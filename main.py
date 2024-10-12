# corntab:
# 0 */12 * * * ~/email-rain-alert/main.py
import requests
import os
import json
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    json_str = re.sub(r'//.*', '', file.read()) # remove "//" comments in JSON
    config = json.loads(json_str)
    owm_api_key = config.get("OWM_API_KEY")
    g_app_passwd = config.get("G_app_passwd")
    sender_name = config.get("sender_name")
    sender_email = config.get("sender_email")
    recipients = config.get("recipients", [])  # List of recipients (default to empty list if not found)


OWM_API_KEY= config['OWM_API_KEY'] # generate from api.openweathermap.org

def send_email(subject, body, sender_name, sender_email, recipients, password):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f'{sender_name} <{sender_email}>'
    msg['To'] = ', '.join(recipients)
    msg.attach(MIMEText(body, 'html '))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender_email, password)
       smtp_server.sendmail(sender_email, recipients, msg.as_string())
    print("Message sent:")
    print(msg)

def get_hourly_report(latitude, longitude):
    weather_params = {
            "lat": latitude,
            "lon": longitude,
            "appid": OWM_API_KEY,
            "exclude": "current,minutely,daily,alerts",
    }
    response = requests.get(url="https://api.openweathermap.org/data/3.0/onecall", params=weather_params)
    response.raise_for_status()
    weather_data = response.json()
    return weather_data


def if_will_rain(latitude, longitude):
    weather_data = get_hourly_report(latitude, longitude)
    dprint(weather_data)
    will_rain_after_hour={}
    loc_timezone = weather_data["timezone"]
    for hour_count, hour_data in enumerate(weather_data["hourly"]):
        condition_code = hour_data["weather"][0]["id"]
        if int(condition_code) < 700:
            will_rain_after_hour[hour_count] = hour_data
    return will_rain_after_hour, loc_timezone


def send_rain_email(will_rain_after_hour, location_name, latitude, longitude, loc_timezone, recipients):
    dprint(will_rain_after_hour)
    rain_time = ""
    body = ""
    timezone = loc_timezone
    for rain_hour, hour_data in will_rain_after_hour.items():
        rain_time =  rain_time + " "+ str(rain_hour)
        print(rain_hour, hour_data)
        readable_rain_time = convert_timestamp_to_readable(hour_data["dt"], timezone)
        body += "<b>" + readable_rain_time  + "</b> <br>" + pprint.pformat(hour_data) + "<br>"
    ## Add a link to other source (US GOV)
    body += "<b>Other reference:</b> <br>"
    body += "https://forecast.weather.gov/MapClick.php?lon=" + longitude + "&lat=" + latitude
    send_email(location_name + " 雨:"+rain_time, body,
         config['sender_name'], config['sender_email'], recipients, config['G_app_passwd'])


def rain_alert(location_name, latitude, longitude, recipients):
    will_rain_after_hour, loc_timezone = if_will_rain(latitude, longitude)
    if will_rain_after_hour:
        send_rain_email(will_rain_after_hour, location_name, latitude, longitude, loc_timezone, recipients)


def test_rain_alert(location_name, latitude, longitude, recipients):
    will_rain_after_hour, loc_timezone = if_will_rain(latitude, longitude)
    send_rain_email(will_rain_after_hour, location_name, latitude, longitude, loc_timezone, recipients)


if __name__=="__main__":
    for recipient in recipients:
        location_name = recipient.get("location_name")
        latitude = recipient.get("latitude")
        longitude = recipient.get("longitude")
        recipients_email = recipient.get("recipients_email", [])  # List of emails
        if latitude != "" :
            rain_alert(location_name, latitude, longitude, recipients_email)
            ## Enable if need test 
            if recipient.get("tester") : test_rain_alert(location_name, latitude, longitude, recipients_email)



