"""corntab:
    0 */1 * * * python3 ~/email-rain-alert/main.py
"""
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

hour_limit = 24 # choose how many hour you want to predict

def dprint(var, msg=""):
    #print("debug: ", msg, var)
    pass


def convert_timestamp_to_readable(timestamp, timezone_name):
    # Convert the timestamp to a datetime object in UTC
    dt_utc = datetime.fromtimestamp(timestamp, tz=ZoneInfo('UTC'))

    # Convert to the desired timezone
    dt_local = dt_utc.astimezone(ZoneInfo(timezone_name))

    # Return the readable format
    return dt_local.strftime('%Y-%m-%d %H:%M:%S') # if want timezone, add  %Z%z

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
    # Normalize: always treat recipients as a list
    if isinstance(recipients, str):
        recipients = [recipients]
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
        if hour_count >= hour_limit :
            break
        if int(condition_code) < 700:
            will_rain_after_hour[hour_count] = hour_data
    return will_rain_after_hour, loc_timezone

def get_rain_periods(will_rain_after_hour) :
    """
    Want: rain_periods in two forms: after how many hours, and exact time(human readable)
    """
    rain_periods_in_hour = []
    rain_periods_exact_time  = []
    period = {"start": {}, "end": {}}
    for rain_hour, hour_data in will_rain_after_hour.items():
        if period["start"] == {} :
            period["start"]["hour"] = rain_hour
            period["end"]["hour"] = rain_hour
            period["start"]["time"] = hour_data["dt"]
            period["end"]["time"] = hour_data["dt"]
            continue
        if rain_hour - period["end"]["hour"] <= 1 :
            period["end"]["hour"] =rain_hour
            period["end"]["time"] = hour_data["dt"]
        else :
            rain_periods_in_hour.append((period["start"]["hour"], period["end"]["hour"]))
            rain_periods_exact_time.append((period["start"]["time"], period["end"]["time"]))
            period = {"start": {}, "end": {}}
    # at the end, if the period was not cleaned, it means that this last period was not record
    if (period["start"]) != {} : 
        rain_periods_in_hour.append((period["start"]["hour"], period["end"]["hour"]))
        rain_periods_exact_time.append((period["start"]["time"], period["end"]["time"]))
    return rain_periods_in_hour, rain_periods_exact_time


def send_rain_email(will_rain_after_hour, loc_timezone, r):
    dprint(will_rain_after_hour)
    body = ""
    timezone = loc_timezone
    rain_periods_in_hour, rain_periods_exact_time = get_rain_periods(will_rain_after_hour)
    for time_period in rain_periods_exact_time :
        body += "<b>" \
                + convert_timestamp_to_readable(time_period[0], timezone) \
                + "--" + convert_timestamp_to_readable(time_period[1], timezone) \
                + "</b> <br>"
    ## Add a link to other source (US GOV)
    body += "<br><b>Other reference:</b> <br>"
    body += "https://forecast.weather.gov/MapClick.php?lon=" + str(r["lon"]) + "&lat=" + str(r["lat"]) + "<br>"
    ## Raw data
    body += "<br><b>Raw data:</b><br>" + pprint.pformat(will_rain_after_hour).replace('\n', '<br>')
    rain_periods_in_hour_str = " "
    for p in rain_periods_in_hour :
        rain_periods_in_hour_str += str(p[0]) + "-" + str(p[1]) + " "
    subject = f"{r['location_name']} 雨:{rain_periods_in_hour_str}"
    for recipient in r["recipients_email"]:
        send_email(
                subject,
                body,
                config['sender_name'],
                config['sender_email'],
                recipient,
                config['G_app_passwd']
                )


def rain_alert(recipient):
    latitude = recipient['lat']
    longitude = recipient['lon']
    will_rain_after_hour, loc_timezone = if_will_rain(latitude, longitude)

    # Check if we should run check for this recipient at this hour
    if "check_time" in recipient:
        # Get current hour in the location's timezone
        dt_utc = datetime.now(ZoneInfo('UTC'))
        dt_local = dt_utc.astimezone(ZoneInfo(loc_timezone))
        current_hour_local = dt_local.hour

        if current_hour_local not in recipient["check_time"]:
            print(f"Skipping {recipient.get('location_name', 'location')} because current hour {current_hour_local} (in {loc_timezone}) is not in check_time {recipient['check_time']}")
            return

    if len(will_rain_after_hour) > 1 : 
        send_rain_email(will_rain_after_hour, loc_timezone, recipient)
        print("Rain alert sent to:", recipient['recipients_email'])
    else:
        print("No rain for:", recipient['recipients_email'])

# Iterate over locations from config
for recipient in recipients:
    dprint(f"Checking rain for {recipient.get('location_name', 'location')}")
    rain_alert(recipient)

"""
Logic:
Read every recipient info
Check if will rain
Send email if will rain, customize everything by preference


"""



