import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2
from datetime import datetime, timedelta, time
import json


# ---------------------------
# Funcions d'utilitat
# ---------------------------
comments_file = "data/comments.json"

@st.cache_data
def load_data():
    """Carregar dades GTFS."""
    stops = pd.read_csv("data/stops.txt")
    stop_times = pd.read_csv("data/stop_times.txt")
    trips = pd.read_csv("data/trips.txt")
    calendar_dates = pd.read_csv("data/calendar_dates.txt")
    routes = pd.read_csv("data/routes.txt")
    access = pd.read_csv("data/access.csv")
    return stops, stop_times, trips, calendar_dates, routes, access


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calcular distància entre dues coordenades geogràfiques (en km)."""
    R = 6371  # Radi de la Terra en km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def preprocess_stop_times(stop_times):
    """Arreglar formats horaris GTFS i convertir-los a datetime."""
    def fix_gtfs_time_format(time_str):
        hours, minutes, seconds = map(int, time_str.split(":"))
        if hours >= 24:
            hours -= 24
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    
    stop_times['departure_time'] = stop_times['departure_time'].apply(fix_gtfs_time_format)
    stop_times['departure_time'] = pd.to_datetime(stop_times['departure_time'], format='%H:%M:%S')
    return stop_times

def get_upcoming_trips(nearest_stop, stop_times, trips, calendar_dates, vies):
    end_day = time(23, 59, 59)
    now = datetime.now()
    now_time = now.time()

    time_interval = st.selectbox("Selecciona l'interval de temps:", [1, 2, 12, 24], index=1, help="Escull l'interval de temps en minuts.")
    user_end_datetime = now + timedelta(hours=time_interval)

    # Check if the user_end_time is beyond midnight (next day)
    if user_end_datetime.date() > now.date():
        end_time = end_day
    else:
        end_time = user_end_datetime.time()


    stop_times = preprocess_stop_times(stop_times)
    calendar_dates['date'] = pd.to_datetime(calendar_dates['date'], format='%Y%m%d').dt.date

    #AQUI
    
    selected_date = st.date_input("Selecciona una data:", value=now.date(), help="Si no selecciones cap data, es farà servir la data d'avui.")

# Si l'usuari no selecciona cap data, fem servir la data actual
    if selected_date is None:
        current_date = datetime.now().date()
    else:
        current_date = selected_date
        calendar_today = calendar_dates[calendar_dates['date'] == selected_date]
        trips['trip_service_id'] = trips['trip_id'].str.split('|').str[0]
        valid_trips = trips[trips['service_id'].isin(calendar_today['service_id'])]
    
    # Filtrar horaris per l'estació més propera i l'interval de temps
    upcoming_trips = stop_times[
        (stop_times['stop_id'] == nearest_stop['stop_id']) &
        (stop_times['departure_time'].dt.time > now_time) &
        (stop_times['departure_time'].dt.time <= end_time)
    ]
    
    upcoming_trips['departure_time'] = upcoming_trips['departure_time'].dt.strftime('%H:%M:%S')  # Format HH:MM:SS departure
    upcoming_trips = upcoming_trips.merge(valid_trips, on="trip_id").sort_values("departure_time")
    upcoming_trips = upcoming_trips.merge(routes[['route_id', 'route_long_name']], on='route_id', how='left')

    # Afegir la columna 'via' basada en la selecció de la via
    upcoming_trips['via'] = upcoming_trips.apply(
    lambda row: (
        "1" if ' - ' in row['route_long_name'] and row['trip_headsign'] == row['route_long_name'].split(' - ')[1] 
        else "2" if ' - ' in row['route_long_name'] and row['trip_headsign'] != row['route_long_name'].split(' - ')[1] 
        else "Desconegut"
    ),
    axis=1
)

    # Filtrar per via (igual que abans)
    if vies == 1:
        indices_to_drop = []
        for i in range(len(upcoming_trips)):
            line = upcoming_trips['route_id'].iloc[i]
            headsign = upcoming_trips['trip_headsign'].iloc[i]
            route_long_name = routes[routes['route_id'] == line]['route_long_name'].values[0]
            if ' - ' in route_long_name:
                destination = route_long_name.split(' - ')[1]
                if headsign != destination:
                    indices_to_drop.append(i)
        upcoming_trips = upcoming_trips.drop(indices_to_drop)

    if vies == 2:
        indices_to_drop = []
        for i in range(len(upcoming_trips)):
            line = upcoming_trips['route_id'].iloc[i]
            headsign = upcoming_trips['trip_headsign'].iloc[i]
            route_long_name = routes[routes['route_id'] == line]['route_long_name'].values[0]
            if ' - ' in route_long_name:
                destination = route_long_name.split(' - ')[1]
                if headsign == destination:
                    indices_to_drop.append(i)
        upcoming_trips = upcoming_trips.drop(indices_to_drop)

    upcoming_trips = upcoming_trips.reset_index(drop=True)
    return upcoming_trips

# -------------------------------------------
# Funció per mostrar la selecció de temps i viatges
# -------------------------------------------

def show_info(nearest_stop):
    vies = 0
    #HORARIS
    st.markdown("## Horaris")
    
    # Selector per triar l'interval de temps
    
    
    # Botons per a triar la via
    all, via1, via2, accessibilitat = st.columns(4)
    
    if "selected_option" not in st.session_state:
        st.session_state["selected_option"] = None

    with all:
        if st.button("Totes les vies"):
            st.session_state["selected_option"] = "all"
    with via1:
        if st.button("Via 1"):
            st.session_state["selected_option"] = "via1"
    with via2:
        if st.button("Via 2"):
            st.session_state["selected_option"] = "via2"
    with accessibilitat:
        if st.button("Accessibilitat"):
            st.session_state["selected_option"] = "accessibilitat"
    
    # Logic per triar la via
    if st.session_state["selected_option"] == "all":
        vies = 0
    elif st.session_state["selected_option"] == "via1":
        vies = 1
    elif st.session_state["selected_option"] == "via2":
        vies = 2
    elif st.session_state["selected_option"] == "accessibilitat":
        show_access(nearest_stop['stop_id'])
        return

    # Obtenir els viatges amb el nou interval de temps
    upcoming_trips = get_upcoming_trips(nearest_stop, stop_times, trips, calendar_dates, vies)
    
    if upcoming_trips.empty:
        st.write(f"No hi ha viatges previstos")
    else:
        # Mostrar la taula amb els noms de columna modificats
        column_titles = {
            "departure_time": "Hora de sortida",
            "route_id": "Línia",
            "trip_headsign": "Destí",
            "via": "Via"
        }
        st.table(upcoming_trips.rename(columns=column_titles)[["Hora de sortida", "Línia", "Destí", "Via"]])

def select_station_list():
    station_options = stops['stop_name'].tolist() #LLISTA D'ESTACIONS

    selected_station_name = st.selectbox("Selecciona una estació de la llista", station_options) # SELECTOR LLISTA

    selected_stop = stops[stops['stop_name'] == selected_station_name].iloc[0] #DEFINIR ESTACIÓ SELECCIONADA)

    return selected_stop

def select_station_map():
    nearest_stop = None
    m = folium.Map(location=[41.3888, 2.159], zoom_start=11)
    for _, stop in stops.iterrows():
        folium.Marker(
            location=[stop["stop_lat"], stop["stop_lon"]],
            popup=f"{stop['stop_name']} (ID: {stop['stop_id']})",
            icon=folium.Icon(color='blue')
        ).add_to(m)
    
    # Mostrar el mapa a Streamlit
    map_data = st_folium(m, width=1000, height=400)

    stop_msg = "Fes clic al mapa per escollir una estació."
    distance_msg = "La distància es calcularà respecte a la ubicació clicada." 
    # Si es fa clic al mapa, trobar l'estació més propera
    if map_data and map_data['last_clicked']:
        lat, lon = map_data['last_clicked']['lat'], map_data['last_clicked']['lng']

        # Trobar l'estació més propera a la ubicació clicada
        stops["distance"] = stops.apply(lambda row: calculate_distance(lat, lon, row["stop_lat"], row["stop_lon"]), axis=1)
        nearest_stop = stops.loc[stops["distance"].idxmin()]

        stop_msg = (f"{nearest_stop['stop_name']}")
        distance_msg = (f"**Distància:** {nearest_stop['distance']:.2f} km")
    
    col1, col2, = st.columns([1, 1])
    with col1:
        st.write(stop_msg)
    with col2:
        st.write(distance_msg)

    return nearest_stop


def geotren():
    st.subheader("Geotren")
    st.markdown("""
    <iframe title="Geotren" width="800" height="600" 
            src="https://geotren.fgc.cat" 
            frameborder="0" tabindex="1" scrolling="yes"></iframe>
    """, unsafe_allow_html=True)


def load_comments():
    try:
        with open(comments_file, "r") as file:
            comments_data = json.load(file)
            # Convertim el timestamp de nou a datetime
            for service in comments_data:
                for comment in comments_data[service]:
                    try:
                        # Intentem convertir amb fracció de segon
                        comment["timestamp"] = datetime.strptime(comment["timestamp"], "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        # Si no té fracció de segon, utilitzem el format sense fracció
                        comment["timestamp"] = datetime.strptime(comment["timestamp"], "%Y-%m-%d %H:%M:%S")
            return comments_data
    except FileNotFoundError:
        return {}

# Funció per guardar els comentaris al fitxer JSON
def save_comments(comments_data):
    with open(comments_file, "w") as file:
        # Guardar els comentaris amb el timestamp com a cadena
        for service in comments_data:
            for comment in comments_data[service]:
                comment["timestamp"] = comment["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f")
        json.dump(comments_data, file, default=str, indent=4)

# Afegeix un comentari per a una estació
def add_comment(service, comment_text, station_name):
    comments_data = load_comments()
    
    # Crear el nou comentari
    comment = {
        "service": service,
        "comment": comment_text,
        "timestamp": datetime.now(),  # Guardem l'objecte datetime
        "station": station_name
    }

    # Afegir el comentari a la llista corresponent
    if service not in comments_data:
        comments_data[service] = []
    
    comments_data[service].append(comment)
    
    # Limitar a 10 comentaris per servei
    if len(comments_data[service]) > 10:
        comments_data[service] = sorted(comments_data[service], key=lambda x: x["timestamp"], reverse=True)
        comments_data[service] = comments_data[service][:10]  # Mantenir només els 10 comentaris més recents

    # Desa els comentaris al fitxer
    save_comments(comments_data)

# Mostra els comentaris per estació i servei
def show_comments(service, station_name):
    comments_data = load_comments()
    
    if service in comments_data:
        # Filtrar els comentaris per estació
        service_comments = [comment for comment in comments_data[service] if comment["station"] == station_name]
        
        if service_comments:
            # Mostrar comentaris en ordre de recents a antics
            for comment in service_comments:
                st.write(f"{comment['timestamp']} - {comment['comment']}")
        else:
            st.write("No hi ha comentaris per aquesta estació.")
    else:
        st.write("No hi ha comentaris per aquest servei.")

# Funció per mostrar la informació d'accessibilitat i comentaris
def show_access(station):
    # Carregar la informació d'accessibilitat del fitxer access.csv (ajustat segons el teu codi)
    filtered_data = access[access['stop_id'] == station]
    
    # Mapping de les dades de 'wheelchair_boarding' i 'wc'
    wheelchair_boarding_msg = {
        1: "Viable",
        0: "No garantit",
        None: "Sense informació"
    }
    
    wc_msg = {
        3: "Disponible i net :)",
        2: "Disponible",
        1: "Només sota demanda",
        0: "No",
        -1: "Sense informació"
    }
    
    # Substituir els valors en el dataframe amb els missatges corresponents
    filtered_data["wheelchair_boarding"] = filtered_data["wheelchair_boarding"].map(wheelchair_boarding_msg)
    filtered_data["wc"] = filtered_data["wc"].map(wc_msg)

    # Mostrar la informació d'accessibilitat
    filtered_data_renamed = filtered_data.rename(
        columns={
            "wheelchair_boarding": "Cadira de rodes",
            "wc": "Banys"
        })
    st.table(filtered_data_renamed[["Cadira de rodes", "Banys"]])

    # Formulari per recollir comentaris
    service_type = st.selectbox("Selecciona el servei que vols puntuar:", ["Lavabos", "Accessibilitat", "Altres"])
    comment_text = st.text_area("Deixa el teu comentari:")

    if st.button("Publicar comentari"):
        if comment_text:
            add_comment(service_type, comment_text, station)  # Afegir el comentari i guardar-lo
            st.success("Comentari afegit amb èxit!")
        else:
            st.warning("Per favor, escriu un comentari abans de publicar.")

    # Mostrar els comentaris
    show_comments(service_type, station)
    
# ---------------------------
# Execució de l'aplicació
# ---------------------------

st.title("FGC")
stops, stop_times, trips, calendar_dates, routes, access = load_data()

# Iniciar l'estat de sessió si no existeix
if "menu_level_1" not in st.session_state:
    st.session_state["menu_level_1"] = "Buscador"
if "menu_level_2" not in st.session_state:
    st.session_state["menu_level_2"] = "Mapa"
if "selected_stop" not in st.session_state:
    st.session_state["selected_stop"] = None

# --- MENÚ NIVELL 1: "Buscador", "Geotren" o "Altres" ---
bus, geo, altres = st.columns(3)
with bus:
    if st.button("Buscador"):
        st.session_state["menu_level_1"] = "Buscador"
        st.session_state["menu_level_2"] = "Mapa"  # Resetar submenú
with geo:
    if st.button("Geotren"):
        st.session_state["menu_level_1"] = "Geotren"
with altres:
    if st.button("Altres"):
        st.session_state["menu_level_1"] = "Altres"

# --- Opcions per a "Buscador" ---
if st.session_state["menu_level_1"] == "Buscador":

    #llista o mapa
    mapa, llista = st.columns(2)
    with mapa:
        if st.button("Mapa"):
            st.session_state["menu_level_2"] = "Mapa"
    with llista:
        if st.button("Llista"):
            st.session_state["menu_level_2"] = "Llista"

    # --- Si es selecciona "Mapa" ---
    if st.session_state["menu_level_2"] == "Mapa":
        st.session_state["selected_stop"] = select_station_map()  # Seleccionar estació al mapa
        if st.session_state["selected_stop"] is not None:
            show_info(st.session_state["selected_stop"])  # Mostrar info de l'estació


    # --- Si es selecciona "Llista" ---
    elif st.session_state["menu_level_2"] == "Llista":
        st.session_state["selected_stop"] = select_station_list()  # Seleccionar estació de la llista
        if st.session_state["selected_stop"] is not None:
            show_info(st.session_state["selected_stop"])  # Mostrar info de l'estació

# --- Opcions per a "Geotren" ---
elif st.session_state["menu_level_1"] == "Geotren":
    geotren()

# --- Opcions per a "Altres" ---
elif st.session_state["menu_level_1"] == "Altres":
    st.write("Altres opcions pendents d'implementar.")