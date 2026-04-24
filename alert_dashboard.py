"""
alert_dashboard.py — updated layout

Pie, Bar, and Line charts in one row.
Large map visualization below.
"""

import sqlite3
import pandas as pd
from dash import Dash, dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.express as px
import dash_bootstrap_components as dbc

DB_FILE = "delivery.db"

def fetch_alert_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT 
            product,
            alert_type,
            value,
            latitude,
            longitude,
            accel_g,
            temperature,
            rain_raw,
            timestamp
        FROM alerts
        ORDER BY datetime(timestamp) DESC
    """, conn)
    conn.close()
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


app = Dash(__name__, external_stylesheets=[dbc.themes.SANDSTONE])
app.title = "IoT Alert Analytics Dashboard"

app.layout = dbc.Container([
    html.H2("📊 IoT Product Alert Dashboard", className="text-center my-3"),
    html.Hr(),

    # --- KPIs ---
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Total Alerts"),
            dbc.CardBody(html.H4(id="total-alerts", className="card-text"))
        ], color="primary", inverse=True), width=3),

        dbc.Col(dbc.Card([
            dbc.CardHeader("Unique Products"),
            dbc.CardBody(html.H4(id="unique-products", className="card-text"))
        ], color="info", inverse=True), width=3),

        dbc.Col(dbc.Card([
            dbc.CardHeader("Alert Types"),
            dbc.CardBody(html.H4(id="alert-types", className="card-text"))
        ], color="warning", inverse=True), width=3),

        dbc.Col(dbc.Card([
            dbc.CardHeader("Most Recent Alert"),
            dbc.CardBody(html.H5(id="latest-alert", className="card-text"))
        ], color="danger", inverse=True), width=3),
    ], className="mb-4"),

    # --- Charts Row ---
    dbc.Row([
        dbc.Col(dcc.Graph(id="alerts-by-product"), md=4),
        dbc.Col(dcc.Graph(id="alerts-by-type"), md=4),
        dbc.Col(dcc.Graph(id="alerts-over-time"), md=4),
    ], className="mb-4"),

    # --- Large Map ---
    html.H4("Alert Locations (Perambur, Chennai)", className="mt-4"),
    dbc.Row([
        dbc.Col(dcc.Graph(id="alert-map", style={"height": "550px"}), width=12)
    ], className="mb-5"),

    # --- Table ---
    html.H4("Recent Alerts Table", className="mt-4"),
    dash_table.DataTable(
        id="alerts-table",
        columns=[
            {"name": "Product", "id": "product"},
            {"name": "Type", "id": "alert_type"},
            {"name": "Value", "id": "value"},
            {"name": "Temperature (°C)", "id": "temperature"},
            {"name": "Accel (g)", "id": "accel_g"},
            {"name": "Rain Raw", "id": "rain_raw"},
            {"name": "Time", "id": "timestamp"}
        ],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "center"},
        page_size=10
    ),

    # --- Auto-refresh ---
    dcc.Interval(id="update-interval", interval=10 * 1000, n_intervals=0)
], fluid=True)


@app.callback(
    [
        Output("total-alerts", "children"),
        Output("unique-products", "children"),
        Output("alert-types", "children"),
        Output("latest-alert", "children"),
        Output("alerts-by-product", "figure"),
        Output("alerts-by-type", "figure"),
        Output("alerts-over-time", "figure"),
        Output("alert-map", "figure"),
        Output("alerts-table", "data")
    ],
    Input("update-interval", "n_intervals")
)
def update_dashboard(_):
    df = fetch_alert_data()
    if df.empty:
        empty_fig = px.scatter(title="No Data Found")
        return 0, 0, 0, "N/A", empty_fig, empty_fig, empty_fig, empty_fig, []

    total_alerts = len(df)
    unique_products = df["product"].nunique()
    alert_types = df["alert_type"].nunique()
    latest_alert = f"{df.iloc[0]['product']} - {df.iloc[0]['alert_type']}"

    # --- Charts ---
    fig_product = px.bar(df.groupby("product").size().reset_index(name="count"),
                         x="product", y="count", title="Alerts by Product")

    fig_type = px.pie(df, names="alert_type", title="Alerts by Type", hole=0.3)

    df_time = df.groupby(pd.Grouper(key="timestamp", freq="1H")).size().reset_index(name="count")
    fig_time = px.line(df_time, x="timestamp", y="count", markers=True,
                       title="Alerts Over Time (Hourly)")

    # --- Map ---
    if "latitude" in df.columns and "longitude" in df.columns:
        fig_map = px.scatter_mapbox(df, lat="latitude", lon="longitude",
                                    color="alert_type", hover_name="product",
                                    zoom=13, height=550,
                                    title="Alert Locations (Perambur, Chennai)",
                                    mapbox_style="open-street-map")
    else:
        fig_map = px.scatter(title="No Location Data Available")

    df_recent = df.head(20).to_dict("records")

    return (total_alerts, unique_products, alert_types, latest_alert,
            fig_product, fig_type, fig_time, fig_map, df_recent)


if __name__ == "__main__":
    app.run(debug=True)
