import time
import csv
import os
import numpy as np
import requests
import jwt
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from max30102 import MAX30102
from scipy.signal import find_peaks

API_KEY = 'K9DACC6D0SPCIO0G'
THINGSPEAK_URL = 'https://api.thingspeak.com/update'

JWT_SECRET = '9f2h3$%G2kDb!@jV#h3@iX8wLq0p34Tj'
JWT_ALGORITHM = 'HS256'
JWT_EXP_DELTA_SECONDS = 3600

CSV_FILE = 'data.csv'

def generate_jwt():
    """Generate a JWT token for secure access."""
    payload = {
        'device': 'max30102_sensor',
        'exp': time.time() + JWT_EXP_DELTA_SECONDS
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def calculate_bpm(ir_data, sampling_rate=100):
    ir_data = np.array(ir_data)
    peaks, _ = find_peaks(ir_data, distance=sampling_rate/2, height=np.mean(ir_data))
    if len(peaks) > 1:
        intervals = np.diff(peaks) / sampling_rate
        return 60 / np.mean(intervals)
    return None

def calculate_spo2(red_data, ir_data):
    red_ac, red_dc = np.std(red_data), np.mean(red_data)
    ir_ac, ir_dc = np.std(ir_data), np.mean(ir_data)
    if ir_dc != 0 and red_dc != 0:
        ratio = (red_ac / red_dc) / (ir_ac / ir_dc)
        return max(0, min(100, 110 - 25 * ratio))
    return None

def upload_to_thingspeak(bpm, spo2):
    payload = {'api_key': API_KEY, 'field1': bpm, 'field2': spo2}
    token = generate_jwt()
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.post(THINGSPEAK_URL, params=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"Uploaded: BPM={bpm:.1f}, SpO₂={spo2:.1f}%")
        else:
            print(f"⚠ Upload failed: {response.status_code}")
    except requests.RequestException as e:
        print(f"❌ Error uploading: {e}")

def write_to_csv(timestamp, bpm, spo2):
    """Append a row of data to CSV_FILE."""
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(['timestamp', 'bpm', 'spo2'])
        writer.writerow([timestamp, bpm, spo2])

def plot_data():
    if not os.path.isfile(CSV_FILE):
        print("No data file found to plot.")
        return
    
    df = pd.read_csv(CSV_FILE, parse_dates=['timestamp'])
    if df.empty:
        print("Data file is empty.")
        return

    plt.figure(figsize=(10, 5))

    plt.subplot(2, 1, 1)
    plt.plot(df['timestamp'], df['bpm'], marker='o', linestyle='-')
    plt.title('BPM over Time')
    plt.xlabel('Timestamp')
    plt.ylabel('BPM')
    plt.grid(True)

    plt.subplot(2, 1, 2)
    plt.plot(df['timestamp'], df['spo2'], marker='o', linestyle='-', color='orange')
    plt.title('SpO₂ over Time')
    plt.xlabel('Timestamp')
    plt.ylabel('SpO₂ (%)')
    plt.grid(True)
    
    plt.tight_layout()
    plt.show()

sensor = MAX30102()
sensor.setup()

print("Monitoring... Place finger on the sensor.")
time.sleep(2)

try:
    while True:
        red_readings, ir_readings = [], []
        for _ in range(500):
            red, ir = sensor.read_fifo()
            if red is not None and ir is not None:
                red_readings.append(red)
                ir_readings.append(ir)
            time.sleep(0.01)

        if red_readings and ir_readings:
            bpm = calculate_bpm(ir_readings)
            spo2 = calculate_spo2(red_readings, ir_readings)
            if bpm and spo2:
                print(f"BPM: {bpm:.1f} | SpO₂: {spo2:.1f}%")
                upload_to_thingspeak(bpm, spo2)

                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                write_to_csv(current_time, bpm, spo2)
            else:
                print("Hold still or reposition finger.")
        else:
            print("No valid data detected. Try again.")
except KeyboardInterrupt:
    print("\nExiting and plotting data...")
    plot_data()
