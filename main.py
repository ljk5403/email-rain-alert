# corntab:
# 0 */12 * * * ~/email-rain-alert/main.py
import requests
import os
import json
import smtplib
from email.mime.text import MIMEText
import pprint
from datetime import datetime
from zoneinfo import ZoneInfo

def dprint(var, msg=""):
    print("debug: ", msg, var)


def convert_timestamp_to_readable(timestamp, timezone_name):
    # Convert the timestamp to a datetime object in UTC
    dt_utc = datetime.fromtimestamp(timestamp, tz=ZoneInfo('UTC'))
    
    # Convert to the desired timezone
    dt_local = dt_utc.astimezone(ZoneInfo(timezone_name))
    
    # Return the readable format
    return dt_local.strftime('%Y-%m-%d %H:%M:%S %Z%z')

# Load the JSON configuration file
with open('config.json', 'r') as file:
    config = json.load(file)

OWM_API_KEY= config['OWM_API_KEY'] # generate from api.openweathermap.org

def send_email(subject, body, sender, recipients, password):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, recipients, msg.as_string())
    print("Message sent!")

def get_hourly_report(latitude, longitude):
    weather_params = {
            "lat": latitude,
            "lon": longitude,
            "appid": OWM_API_KEY,
            "exclude": "current,minutely,daily,alerts", #TODO:?????
    }
    response = requests.get(url="https://api.openweathermap.org/data/3.0/onecall", params=weather_params)
    response.raise_for_status()
    weather_data = response.json()
    return weather_data

#get_hourly_report(43.0876626, -89.3743042)

def if_will_rain(latitude, longitude):
    weather_data = get_hourly_report(latitude, longitude)
    will_rain_after_hour={}
    will_rain_after_hour["timezone"] = weather_data["timezone"]
    for hour_count, hour_data in enumerate(weather_data["hourly"]):
        condition_code = hour_data["weather"][0]["id"]
        if int(condition_code) < 700:
            will_rain_after_hour[hour_count] = hour_data
    return will_rain_after_hour


def send_rain_email(will_rain_after_hour, recipients):
    rain_time = ""
    body = ""
    timezone = will_rain_after_hour["timezone"]
    for rain_hour, hour_data in will_rain_after_hour.items():
        if rain_hour != "timezone":
            rain_time =  rain_time + " "+ str(rain_hour)
            readable_rain_time = convert_timestamp_to_readable(hour_data["dt"], timezone)
            body += readable_rain_time  + "\n" + pprint.pformat(hour_data) + "\n"
    #dprint(body)
    send_email("Rain:"+rain_time, body, config['sender'], recipients, config['G_app_passwd'])


def rain_alert(latitude, longitude, recipients):
    will_rain_after_hour = if_will_rain(latitude, longitude)
    if will_rain_after_hour:
        send_rain_email(will_rain_after_hour, recipients)

#TODO: move location and recipients to config.json
rain_alert(43.0876626, -89.3743042, ["lijiankun5403@gmail.com"]) # Madison



