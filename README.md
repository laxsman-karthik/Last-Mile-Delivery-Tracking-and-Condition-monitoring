# Last Mile Delivery Tracking and Condition Monitoring

An IoT-based system for real-time monitoring of delivery conditions and location during last-mile transportation. This project ensures product safety by detecting environmental risks such as temperature, humidity, vibration, and rain exposure.


## Project Overview

In modern logistics and e-commerce, last-mile delivery is a critical stage where goods are vulnerable to environmental damage. This system uses an ESP32-based IoT solution to continuously monitor conditions and generate alerts when unsafe situations occur.

The system integrates:
- Sensor-based monitoring
- Real-time GPS tracking
- Flask-based backend server
- Driver mobile application
- Supervisor dashboard

## Objectives

- Monitor temperature, humidity, vibration, and rain exposure
- Enable real-time data transmission using Wi-Fi
- Apply product-specific threshold limits
- Send instant alerts using Pushover API
- Store and analyze delivery data using SQLite
- Provide dashboard visualization for supervisors


## Components Used

### Hardware
- ESP32 Microcontroller
- DHT11 (Temperature & Humidity Sensor)
- MPU6050 (Vibration Sensor)
- Rain Sensor (HW-103)
- GPS Module (NEO-6M)
- Power Supply

### Software
- Arduino IDE (ESP32 Programming)
- Python Flask (Backend Server)
- SQLite (Database)
- Kivy (Driver Mobile App)
- Pushover API (Notifications)

### Circuit Diagram
## Implementation

### Hardware Layer
- ESP32 collects sensor data
- Processes and filters readings
- Sends data to server via HTTP

### Server Layer (Flask)
Key API endpoints:
- /get_thresholds → Sends thresholds to ESP32
- /set_products → Stores driver-selected products
- /alert → Receives alerts from ESP32
- /alerts → Displays alert logs

Database stores:
- Product thresholds
- Selected products
- Alert history

### Driver App (Kivy)
- Allows driver to select products
- Sends selection to server
- Enables dynamic threshold configuration

### Dashboard
Displays:
- Alert type
- Product name
- Timestamp
- GPS location


## Working Principle

1. System Initialization – ESP32 initializes sensors and connects to Wi-Fi  
2. Product Selection – Driver selects products using mobile app  
3. Fetch Thresholds – ESP32 retrieves product-specific limits  
4. Data Collection – Sensors continuously collect environmental data  
5. Comparison – Values are checked against thresholds  
6. Alert Generation – Alerts are sent when limits are exceeded  
7. Monitoring – Dashboard displays alerts for supervisors  


## Alert System

Alerts are triggered when:
- Temperature exceeds limits
- Humidity is out of range
- Vibration is too high
- Rain or leakage is detected

Each alert includes:
- Product name
- Alert type
- Sensor value
- GPS coordinates
- Timestamp


## Results

- Real-time location tracking achieved  
- Continuous environmental monitoring  
- Accurate alert generation  
- Improved delivery safety  
- Dashboard enabled route analysis  


## Project Structure

├── server.py  
├── alert_dashboard.py  
├── driver_app.py  
├── esp32_code.ino  
├── delivery.db  
├── images/  
│   └── architecture.png  
└── README.md  


## How to Run

### 1. Start Flask Server
python server.py

### 2. Run Dashboard
python alert_dashboard.py

### 3. Run Driver App
python driver_app.py

### 4. Upload ESP32 Code
- Open Arduino IDE  
- Connect ESP32  
- Upload code  
- Configure Wi-Fi credentials and server IP  

## API Endpoints

| Endpoint         | Method | Description |
|-----------------|--------|------------|
| /init_products  | POST   | Initialize product thresholds |
| /get_products   | GET    | Get available products |
| /set_products   | POST   | Save selected products |
| /get_thresholds | GET    | Send thresholds to ESP32 |
| /alert          | POST   | Receive alerts |
| /alerts         | GET    | Fetch alert history |


## Technologies Used

- IoT (ESP32)
- Embedded Systems
- Flask REST API
- SQLite Database
- Kivy Framework
- GPS Tracking
- Pushover Notifications


## Future Enhancements

- Machine learning for predictive alerts  
- Cloud deployment (AWS/Azure)  
- Mobile dashboard for supervisors  
- Advanced route optimization  
- Battery optimization for IoT device  


## Authors

- Laxsman Karthik S
- Arun S
