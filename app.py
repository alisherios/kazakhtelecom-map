import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
import plotly.express as px
import plotly.graph_objects as go
from flask import Flask, render_template, request, jsonify
import json
import os
import numpy as np

# Создаем Flask приложение
app = Flask(__name__)

# Загружаем данные
@app.route('/')
def index():
    return render_template('index.html')

# Функция для создания базовой карты
def create_base_map():
    # Центр Казахстана примерно
    map_center = [48.0196, 66.9237]
    m = folium.Map(location=map_center, zoom_start=5, 
                   tiles='CartoDB positron', 
                   control_scale=True)
    
    # Добавляем стилизацию в цветах Казахтелеком
    folium.TileLayer(
        tiles='CartoDB positron',
        name='Базовая карта',
        overlay=False,
        control=True
    ).add_to(m)
    
    return m

# Функция для добавления точек на карту
def add_points_to_map(m, df, provider=None):
    # Если выбран провайдер, фильтруем данные
    if provider:
        if provider == 'kt':
            df = df[df['kt_speedtest'] == 1]
        elif provider == 'beeline':
            df = df[df['beeline_speedtest'] == 1]
        elif provider == 'almatv':
            df = df[df['almatv_speedtest'] == 1]
    
    # Создаем кластер маркеров для лучшей производительности
    marker_cluster = MarkerCluster().add_to(m)
    
    # Добавляем точки на карту
    for idx, row in df.iterrows():
        # Пропускаем строки с отсутствующими координатами
        if pd.isna(row['latitude_speedtest']) or pd.isna(row['longitude_speedtest']):
            continue
        
        # Определяем цвет маркера в зависимости от скорости
        if provider == 'kt' or provider is None:
            speed = row['kt_download_speed']
            provider_name = 'Казахтелеком'
        elif provider == 'beeline':
            speed = row['beeline_download_speed']
            provider_name = 'Beeline'
        elif provider == 'almatv':
            speed = row['almatv_download_speed']
            provider_name = 'AlmaTV'
        else:
            speed = max(row['kt_download_speed'], row['beeline_download_speed'], row['almatv_download_speed'])
            provider_name = 'Все провайдеры'
        
        # Определяем цвет в зависимости от скорости
        if speed < 50:
            color = 'red'
            speed_category = 'Низкая'
        elif speed < 100:
            color = 'orange'
            speed_category = 'Средняя'
        else:
            color = 'green'
            speed_category = 'Высокая'
        
        # Создаем всплывающую подсказку
        popup_text = f"""
        <b>Адрес:</b> {row['address']}<br>
        <b>Провайдер:</b> {provider_name}<br>
        <b>Скорость загрузки:</b> {speed:.2f} Мбит/с<br>
        <b>Категория скорости:</b> {speed_category}<br>
        """
        
        if provider == 'kt' or provider is None:
            popup_text += f"<b>Скорость выгрузки KT:</b> {row['kt_upload_speed']:.2f} Мбит/с<br>"
        if provider == 'beeline' or provider is None:
            popup_text += f"<b>Скорость выгрузки Beeline:</b> {row['beeline_upload_speed']:.2f} Мбит/с<br>"
        if provider == 'almatv' or provider is None:
            popup_text += f"<b>Скорость выгрузки AlmaTV:</b> {row['almatv_upload_speed']:.2f} Мбит/с<br>"
        
        folium.Marker(
            location=[row['latitude_speedtest'], row['longitude_speedtest']],
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=f"{row['address']} - {speed:.2f} Мбит/с",
            icon=folium.Icon(color=color, icon='wifi', prefix='fa')
        ).add_to(marker_cluster)
    
    return m

# Функция для создания тепловой карты по скорости
def create_speed_heatmap(m, df, provider=None):
    # Если выбран провайдер, фильтруем данные и выбираем соответствующий столбец скорости
    if provider == 'kt':
        speed_column = 'kt_download_speed'
        df = df[df['kt_speedtest'] == 1]
    elif provider == 'beeline':
        speed_column = 'beeline_download_speed'
        df = df[df['beeline_speedtest'] == 1]
    elif provider == 'almatv':
        speed_column = 'almatv_download_speed'
        df = df[df['almatv_speedtest'] == 1]
    else:
        # Если провайдер не выбран, используем максимальную скорость из всех провайдеров
        df['max_speed'] = df[['kt_download_speed', 'beeline_download_speed', 'almatv_download_speed']].max(axis=1)
        speed_column = 'max_speed'
    
    # Подготавливаем данные для тепловой карты
    heat_data = []
    for idx, row in df.iterrows():
        # Пропускаем строки с отсутствующими координатами или скоростью
        if pd.isna(row['latitude_speedtest']) or pd.isna(row['longitude_speedtest']) or pd.isna(row[speed_column]):
            continue
        
        # Добавляем вес (скорость) для каждой точки
        heat_data.append([row['latitude_speedtest'], row['longitude_speedtest'], row[speed_column]])
    
    # Создаем тепловую карту
    HeatMap(
        heat_data,
        radius=15,
        blur=10,
        gradient={0.2: 'blue', 0.4: 'cyan', 0.6: 'lime', 0.8: 'yellow', 1: 'red'},
        name='Тепловая карта по скорости',
        control=True,
        show=False
    ).add_to(m)
    
    return m

# Функция для создания тепловой карты по плотности
def create_density_heatmap(m, df, provider=None):
    # Если выбран провайдер, фильтруем данные
    if provider == 'kt':
        df = df[df['kt_speedtest'] == 1]
    elif provider == 'beeline':
        df = df[df['beeline_speedtest'] == 1]
    elif provider == 'almatv':
        df = df[df['almatv_speedtest'] == 1]
    
    # Подготавливаем данные для тепловой карты плотности
    heat_data = []
    for idx, row in df.iterrows():
        # Пропускаем строки с отсутствующими координатами
        if pd.isna(row['latitude_speedtest']) or pd.isna(row['longitude_speedtest']):
            continue
        
        # Для карты плотности вес одинаковый для всех точек
        heat_data.append([row['latitude_speedtest'], row['longitude_speedtest'], 1])
    
    # Создаем тепловую карту плотности
    HeatMap(
        heat_data,
        radius=15,
        blur=10,
        gradient={0.2: 'blue', 0.4: 'green', 0.6: 'yellow', 0.8: 'orange', 1: 'red'},
        name='Тепловая карта по плотности',
        control=True,
        show=False
    ).add_to(m)
    
    return m

# Маршрут для получения данных для карты
@app.route('/get_map', methods=['GET'])
def get_map():
    # Получаем параметры фильтрации из запроса
    provider = request.args.get('provider', None)
    min_speed = float(request.args.get('min_speed', 0))
    max_speed = float(request.args.get('max_speed', 1000))
    map_type = request.args.get('map_type', 'points')  # points, speed_heatmap, density_heatmap
    
    # Загружаем данные
    df = pd.read_excel('/home/ubuntu/upload/cbm_st_pro_1.xlsx')
    
    # Фильтруем по скорости
    if provider == 'kt':
        df = df[(df['kt_download_speed'] >= min_speed) & (df['kt_download_speed'] <= max_speed)]
    elif provider == 'beeline':
        df = df[(df['beeline_download_speed'] >= min_speed) & (df['beeline_download_speed'] <= max_speed)]
    elif provider == 'almatv':
        df = df[(df['almatv_download_speed'] >= min_speed) & (df['almatv_download_speed'] <= max_speed)]
    else:
        # Для всех провайдеров фильтруем по максимальной скорости
        df['max_speed'] = df[['kt_download_speed', 'beeline_download_speed', 'almatv_download_speed']].max(axis=1)
        df = df[(df['max_speed'] >= min_speed) & (df['max_speed'] <= max_speed)]
    
    # Создаем базовую карту
    m = create_base_map()
    
    # Добавляем соответствующий слой в зависимости от типа карты
    if map_type == 'points':
        m = add_points_to_map(m, df, provider)
    elif map_type == 'speed_heatmap':
        m = create_speed_heatmap(m, df, provider)
    elif map_type == 'density_heatmap':
        m = create_density_heatmap(m, df, provider)
    
    # Добавляем контроль слоев
    folium.LayerControl().add_to(m)
    
    # Сохраняем карту во временный файл
    map_file = 'templates/temp_map.html'
    m.save(map_file)
    
    # Читаем содержимое файла
    with open(map_file, 'r') as f:
        map_html = f.read()
    
    return jsonify({'map_html': map_html})

# Маршрут для получения статистики
@app.route('/get_stats', methods=['GET'])
def get_stats():
    # Загружаем данные
    df = pd.read_csv('/home/ubuntu/upload/cbm_st_pro.csv', encoding='latin1')
    
    # Базовая статистика
    stats = {
        'total_points': len(df),
        'providers': {
            'kt': {
                'count': df['kt_speedtest'].sum(),
                'avg_download': df['kt_download_speed'].mean(),
                'avg_upload': df['kt_upload_speed'].mean(),
                'max_download': df['kt_download_speed'].max(),
                'min_download': df['kt_download_speed'].min()
            },
            'beeline': {
                'count': df['beeline_speedtest'].sum(),
                'avg_download': df['beeline_download_speed'].mean(),
                'avg_upload': df['beeline_upload_speed'].mean(),
                'max_download': df['beeline_download_speed'].max(),
                'min_download': df['beeline_download_speed'].min()
            },
            'almatv': {
                'count': df['almatv_speedtest'].sum(),
                'avg_download': df['almatv_download_speed'].mean(),
                'avg_upload': df['almatv_upload_speed'].mean(),
                'max_download': df['almatv_download_speed'].max(),
                'min_download': df['almatv_download_speed'].min()
            }
        },
        'cities': df['isb_town'].value_counts().to_dict()
    }
    
    # Создаем данные для графиков
    
    # 1. Гистограмма распределения скоростей
    kt_hist = px.histogram(df, x='kt_download_speed', nbins=30, 
                          title='Распределение скоростей Казахтелеком',
                          labels={'kt_download_speed': 'Скорость загрузки (Мбит/с)', 'count': 'Количество точек'},
                          color_discrete_sequence=['#0056A4'])
    kt_hist.update_layout(template='plotly_white')
    
    beeline_hist = px.histogram(df, x='beeline_download_speed', nbins=30, 
                               title='Распределение скоростей Beeline',
                               labels={'beeline_download_speed': 'Скорость загрузки (Мбит/с)', 'count': 'Количество точек'},
                               color_discrete_sequence=['#FFCC00'])
    beeline_hist.update_layout(template='plotly_white')
    
    almatv_hist = px.histogram(df, x='almatv_download_speed', nbins=30, 
                              title='Распределение скоростей AlmaTV',
                              labels={'almatv_download_speed': 'Скорость загрузки (Мбит/с)', 'count': 'Количество точек'},
                              color_discrete_sequence=['#FF6600'])
    almatv_hist.update_layout(template='plotly_white')
    
    # 2. Сравнение средних скоростей провайдеров
    providers_comparison = go.Figure()
    providers_comparison.add_trace(go.Bar(
        x=['Казахтелеком', 'Beeline', 'AlmaTV'],
        y=[stats['providers']['kt']['avg_download'], 
           stats['providers']['beeline']['avg_download'], 
           stats['providers']['almatv']['avg_download']],
        name='Скорость загрузки',
        marker_color=['#0056A4', '#FFCC00', '#FF6600']
    ))
    providers_comparison.add_trace(go.Bar(
        x=['Казахтелеком', 'Beeline', 'AlmaTV'],
        y=[stats['providers']['kt']['avg_upload'], 
           stats['providers']['beeline']['avg_upload'], 
           stats['providers']['almatv']['avg_upload']],
        name='Скорость выгрузки',
        marker_color=['#66A3D2', '#FFE066', '#FFAA66']
    ))
    providers_comparison.update_layout(
        title='Сравнение средних скоростей провайдеров',
        xaxis_title='Провайдер',
        yaxis_title='Скорость (Мбит/с)',
        barmode='group',
        template='plotly_white'
    )
    
    # 3. Круговая диаграмма доли провайдеров
    providers_pie = go.Figure(data=[go.Pie(
        labels=['Казахтелеком', 'Beeline', 'AlmaTV'],
        values=[stats['providers']['kt']['count'], 
                stats['providers']['beeline']['count'], 
                stats['providers']['almatv']['count']],
        hole=.3,
        marker_colors=['#0056A4', '#FFCC00', '#FF6600']
    )])
    providers_pie.update_layout(
        title='Доля провайдеров по количеству точек',
        template='plotly_white'
    )
    
    # Преобразуем графики в JSON для передачи на фронтенд
    charts = {
        'kt_hist': kt_hist.to_json(),
        'beeline_hist': beeline_hist.to_json(),
        'almatv_hist': almatv_hist.to_json(),
        'providers_comparison': providers_comparison.to_json(),
        'providers_pie': providers_pie.to_json()
    }
    
    return jsonify({'stats': stats, 'charts': charts})

if __name__ == '__main__':
    # Создаем директорию для шаблонов, если её нет
    os.makedirs('templates', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
