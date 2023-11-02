import requests
import json

class Weatherstack:
    # Allows Weatherstack to hold onto Weatherstack API Key
    # Inputs: Weatherstack API Key
    def __init__(self, weatherstack_key):
        self.key = weatherstack_key

    # Validates a User's Location
    # Inputs: Location
    # Outputs: 0 on Valid Location / -1 on Invalid Location
    def validate_location(self, location):
        request_string = 'http://api.weatherstack.com/current?access_key=' + self.key + '&query=' + location

        r = requests.get(request_string)

        if(r.status_code != 200):
            return -1

        json_data = json.loads(r.content)

        if 'error' in json_data:
            return -1

        return 0

    # Grabs the current weather at a location
    # Inputs: Location
    # Outputs: Weatherstack_Output class with data prefilled / "error" on Weatherstack Error
    def current(self, location):
        request_string = 'http://api.weatherstack.com/current?access_key=' + self.key + '&query=' + location

        try:
            r = requests.get(request_string)
        except:
            return weatherstack_output()
        

        if(r.status_code != 200):
            return "error"

        json_data = json.loads(r.content)
        
        location_data = json_data['location']
        weather_data = json_data['current']

        weather_output = weatherstack_output(
            name = location_data['name'] + ', ' + location_data['region'],
            condition = weather_data['weather_descriptions'],
            temp = weather_data['temperature'],
            humidity = weather_data['humidity'],
            windspeed = weather_data['wind_speed'],
            precip = weather_data['precip'],
            cloudcover = weather_data['cloudcover']
            )

        return weather_output

# Class to format output of the Weatherstack Current function
class weatherstack_output:
    name = ''
    condition = ''
    temp = 0
    humidity = 0
    windspeed = 0
    precip = 0
    cloudcover = 0

    def __init__(self, name, condition, temp, humidity, windspeed, precip, cloudcover):
        self.name = name
        self.condition = condition
        self.temp = temp
        self.humidity = humidity
        self.windspeed = windspeed
        self.precip = precip
        self.cloudcover = cloudcover
