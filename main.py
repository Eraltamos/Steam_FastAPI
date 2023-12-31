from fastapi import FastAPI
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# Crear una instancia de la aplicación FastAPI
app = FastAPI()


# 1 Función para obtener la cantidad de items y porcentaje de contenido gratuito por año
@app.get('/DeveloperFreeContent')
def DeveloperFreeContent(developer: str):

    # Cargamos los archivos Parquet y seleccionamos las columnas necesarias
    steam_games_df = pq.read_table("dataset/steam_games.parquet", columns=['item_id', 'developer', 'release_year', 'price']).to_pandas()

    # Filtrarmos las filas que coinciden con el desarrollador
    developer_df = steam_games_df[steam_games_df['developer'] == developer]

    # Verificamos si el dataFrame está vacío
    if developer_df.empty:
        return {"error": "Desarrollador no encontrado"}

    # Agrupamos los juegos por año de lanzamiento ('release_year') y se realizan dos agregaciones: contar la cantidad de juegos por año ('item_id') y 
    # calculamos el porcentaje de juegos gratuitos ('price' igual a 0) para cada año.
    result = (developer_df.groupby('release_year')
             .agg({'item_id': 'count', 'price': (lambda x: f"{(x == 0).sum() / len(x) * 100:.2f}%" if len(x) > 0 else "0%")})
             .reset_index()
             # Renombramos las columnas resultantes
             .rename(columns={'release_year': 'Año', 'item_id': 'Cantidad de Items', 'price': 'Contenido Free'})
             # Convertimos los datos en una lista de diccionarios
             .to_dict(orient='records'))

    return result


# 2 Función para obtener la cantidad de dinero gastado, %de recomendacion y numero de items del usuario
@app.get("/UserData")
def UserData(user_id: str):

    # Cargamos los archivos parquet y seleccionamos las columnas necesarias
    user_items_df = pq.read_table("dataset/user_items.parquet", columns=['user_id', 'items_count', 'steam_id']).to_pandas()
    user_items_list_df = pq.read_table("dataset/user_items_list.parquet", columns=['steam_id', 'item_id']).to_pandas()
    user_reviews_df = pq.read_table("dataset/user_reviews.parquet", columns=['steam_id', 'recommend']).to_pandas()
    steam_games_df = pq.read_table("dataset/steam_games.parquet", columns=['item_id', 'price']).to_pandas()

    # Filtramos la fila correspondiente al user_id en user_items_df
    user_row = user_items_df[user_items_df['user_id'] == user_id]

    if user_row.empty:
        return {"error": "Usuario no encontrado"}

    # Obtenemos la cantidad de items del usuario
    items_count = user_row['items_count'].iloc[0]

    # Obtenemos el steam_id del usuario
    steam_id = user_row['steam_id'].iloc[0]

    # Filtramos las filas correspondientes a este steam_id en user_items_list_df
    user_item_rows = user_items_list_df[user_items_list_df['steam_id'] == steam_id]

    # Obtenemos los item_ids correspondientes
    item_ids = user_item_rows['item_id']

    # Filtramos las filas correspondientes en steam_games_df y obtener los precios
    prices = steam_games_df[steam_games_df['item_id'].isin(item_ids)]['price']

    # Calculamos el dinero gastado por el usuario
    money_spent = prices.sum()

    # Filtramos las reviews correspondientes a este steam_id
    user_reviews = user_reviews_df[user_reviews_df['steam_id'] == steam_id]

    # Realizamos las operaciones para poder obtener el porcentaje de recomendación
    total_reviews = len(user_reviews)
    recommended_reviews = user_reviews[user_reviews['recommend'] == 1]
    recommendation_percentage = (len(recommended_reviews) / total_reviews) * 100 if total_reviews > 0 else 0

    # El resultado final
    result = {
        "Usuario X": user_id,
        "Dinero gastado": f"{money_spent:.2f} USD",
        "% de recomendación": f"{recommendation_percentage:.2f}%",
        "Cantidad de items": int(items_count)
    }

    return result


#  3 Función para obtener el usuario con mas cantidad de horas jugadas por año de un genero
@app.get('/UserForGenre')
def UserForGenre(genero: str):

    # Cargamos los archivos parquet y las columnas correspondientes
    steam_games_genre_df = pq.read_table("dataset/steam_games_genres.parquet", columns=['item_id', genero]).to_pandas()
    user_items_list_df = pq.read_table("dataset/user_items_list.parquet", columns=['item_id', 'steam_id', 'playtime_forever']).to_pandas()
    steam_games_df = pq.read_table("dataset/steam_games.parquet", columns=['item_id', 'release_year']).to_pandas()
    user_items_df = pq.read_table("dataset/user_items.parquet", columns=['steam_id', 'user_id']).to_pandas()

    # Filtramos los juegos que pertenecen al género especificado
    games_in_genre = steam_games_genre_df[steam_games_genre_df[genero] == 1]

    # Error en caso de que no haya el genero especificado
    if games_in_genre.empty:
        return {"error": "Género no encontrado"}

    # Obtenemos una lista de los item_id de los juegos en el género
    item_ids_in_genre = games_in_genre['item_id'].tolist()

    # Filtramos los registros de user_items_list para obtener las horas jugadas de los juegos en el género
    genre_playtime = user_items_list_df[user_items_list_df['item_id'].isin(item_ids_in_genre)]

    if genre_playtime.empty:
        return {"error": "No hay datos de horas jugadas para este género"}

    # Agregamos las horas jugadas por usuario y año
    user_hours = (genre_playtime
                  .merge(steam_games_df, on='item_id') # Fusionamos genre_playtime con steam_games_df en la columna 'item_id'
                  .merge(user_items_df, left_on='steam_id', right_on='steam_id') # Se fusiona el DataFrame resultante del paso anterior con el DataFrame user_items_df
                  .groupby(['user_id', 'release_year']) # se agrupan los datos por 'user_id' y 'release_year'
                  .agg(Horas=('playtime_forever', 'sum')) # Se calcula la suma de 'playtime_forever' para cada grupo de usuario y año
                  .reset_index()
                  )

    # Encontramos el usuario con más horas jugadas para el género
    user_with_most_playtime = user_hours.groupby('user_id')['Horas'].sum().idxmax()

    # Filtramos las horas jugadas por usuario
    user_hours = user_hours[user_hours['user_id'] == user_with_most_playtime]

    # El resultado final es:
    result = {
        "Usuario con más horas jugadas para Género " + genero: user_with_most_playtime,
        "Horas jugadas": user_hours[['release_year', 'Horas']].to_dict(orient='records')
    }

    return result


# 4 Función para obtener el top 3 de desarrolladoras por año
@app.get("/UsersBestDeveloper")
def UsersBestDeveloper(año: int):

    # Cargamos los archivos Parquet y seleccionar las columnas necesarias
    steam_games_df = pq.read_table("dataset/steam_games.parquet", columns=['item_id', 'release_year', 'developer']).to_pandas()
    user_reviews_df = pq.read_table("dataset/user_reviews.parquet", columns=['item_id', 'recommend', 'sentiment_analysis']).to_pandas()

    # Filtramos el DataFrame de steam_games para obtener los juegos del año dado
    games_of_year = steam_games_df[steam_games_df['release_year'].astype(int) == año]

    if games_of_year.empty:
        return {"error": "No hay juegos para el año especificado"}

    # Filtramos el DataFrame de user_reviews para obtener las reviews recomendadas y positivas
    positive_reviews = user_reviews_df[(user_reviews_df['recommend'] == 1) & (user_reviews_df['sentiment_analysis'] == 2)]

    # Contamos las reviews recomendadas y positivas por juego
    recommendations_per_game = positive_reviews['item_id'].value_counts().reset_index()
    recommendations_per_game.columns = ['item_id', 'recommendation_per_game']

    # Fusionamos los DataFrames de juegos y recomendaciones
    merged_df = games_of_year.merge(recommendations_per_game, on='item_id', how='inner')

    # Calculamos la suma de recomendaciones por desarrollador
    developer_recommendations = merged_df.groupby('developer')['recommendation_per_game'].sum().reset_index()

    # Ordenamos los desarrolladores por recomendaciones en orden descendente
    top_developers = developer_recommendations.nlargest(3, 'recommendation_per_game')

    # El resultado es
    result = [{"Puesto " + str(i + 1): developer} for i, developer in enumerate(top_developers['developer'])]

    return result


# 5 Función para obtener la percepcion segun sentiment_analysis de una desarrolladora en cuanto a positivos o negativos
@app.get("/DeveloperSentimentAnalysis")
def DeveloperSentimentAnalysis(developer: str):

    # Cargar los archivos parquet
    steam_games_df = pq.read_table("dataset/steam_games.parquet", columns=['item_id', 'developer']).to_pandas()
    user_reviews_df = pq.read_table("dataset/user_reviews.parquet", columns=['item_id', 'sentiment_analysis']).to_pandas()

    # Filtramos steam_games para obtener los juegos del desarrollador
    games_of_developer = steam_games_df[steam_games_df['developer'] == developer]

    if games_of_developer.empty:
        return {"error": "Desarrolladora no encontrada"}

    # Filtramos user_reviews para obtener las reviews relacionadas a estos juegos
    reviews_of_developer = user_reviews_df[user_reviews_df['item_id'].isin(games_of_developer['item_id'])]

    if reviews_of_developer.empty:
        return {"error": "No hay reseñas para juegos de esta desarrolladora"}

    # Paso 3: Filtrar las reseñas con sentiment_analysis igual a 2 (positivo) y 0 (negativo)
    positive_reviews = reviews_of_developer[reviews_of_developer['sentiment_analysis'] == 2]
    neutral_reviews = reviews_of_developer[reviews_of_developer['sentiment_analysis'] == 1]
    negative_reviews = reviews_of_developer[reviews_of_developer['sentiment_analysis'] == 0]

    # Paso 4: Contar la cantidad de reseñas positivas y negativas
    positive_count = len(positive_reviews)
    neutral_count = len(neutral_reviews)
    negative_count = len(negative_reviews)

    # Paso 5: Crear el diccionario de resultado
    result = {developer: {"Negative": negative_count, "Neutral": neutral_count, "Positive": positive_count}}

    return result



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)