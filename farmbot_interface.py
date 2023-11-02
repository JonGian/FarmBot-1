import requests
import json
import random
import os
import datetime
import sys
import uuid
from time import sleep
from farmbot import Farmbot
from pytz import timezone
from database_interface import Database

class Farmbot_api:
    # Checks if user exists on Farmbot, and returns API_Key
    # Inputs: User's Email and User's Password
    # Outputs: User's API Key / -1 on Farmbot Error / 0 on Account Error
    def user_account(self, email, password):
        site_data = {'user': {'email': email, 'password': password}}

        request = requests.post('https://my.farm.bot/api/tokens', json = site_data)

        farmbot_data = json.loads(request.content)

        if(request.status_code != 200):
            return -1

        if('token' not in farmbot_data):
            return 0

        user_token = farmbot_data['token']['encoded']
        expiry_date = farmbot_data['token']['unencoded']['exp']

        return (user_token, expiry_date)

    # Grabs a user's Farmbot ID & name
    # Inputs: Header
    # Outputs: Farmbot ID & name 
    def farmbot_info(self, headers):
        r = requests.get('https://my.farm.bot/api/device', headers=headers)

        # Handles if request has failed
        if(r.status_code != 200):
            return "error"

        json_data = json.loads(r.content)
        return json_data

    # Grabs a users plants
    # Inputs: Header
    # Output: List of Plants
    def plants(self, headers):
    
        # Requests Farmbot plant's
        r = requests.get('https://my.farm.bot/api/points', headers=headers)

        # Handles if request has failed
        if(r.status_code != 200):
            return "error"

        # Loads Json into objects
        json_data = json.loads(r.content)

        # Creates a list
        col_values = []

        # Fills list with only plants
        for points in json_data:
            if points['pointer_type'] == 'Plant':
                col_values.append({'id': points['id'], 'name': points['name'], 'x': points['x'],'y': points['y'], 
                                   'device_id': points['device_id'], 'plant_date': points['created_at'], 'openfarm_slug': points['openfarm_slug']})

        return col_values
    
    def get_plant_groups(self, user_email, database : Database, headers):
            r = requests.get('https://my.farm.bot/api/point_groups/', headers=headers)
            data = json.loads(r.content)
            db_vals = []
            for group in data:
                val = {'groupID': group['id'], 'groupName': group['name']}
                if ('pointer_type' in group['criteria']['string_eq']) and group['criteria']['string_eq']['pointer_type'][0] == 'Plant': # plant group
                    plants = []
                    if 'openfarm_slug' in group['criteria']['string_eq']: # plants in the group
                        for plant in group['criteria']['string_eq']['openfarm_slug']:
                            plants.append(plant)
                    else: # otherwise add all
                        all_plants = database.get_plant_openfarmslug(user_email)
                        for v in all_plants:
                            plants.append(v[0])
                        pass
                    val['plants'] = plants
                db_vals.append(val)
            return db_vals
                
                        
                    

    # Grabs a users images of plants
    # Inputs: Header, Amount of Images
    # Outputs: List of Image Names
    def plant_images(self, headers, x,y):

        r = requests.get('https://my.farm.bot/api/images', headers=headers)

        if(r.status_code != 200):
            return "error"

        json_data = json.loads(r.content)

        #Grab lastest image only
        for image in json_data:
            if round(image['meta']['x']) == x or image['meta']['y'] != y:
                url = image['attachment_url']
                date = image['created_at']
                date_time = datetime.datetime.fromisoformat(date[:-1])

                response = requests.get(url)
                orig_name = str(uuid.uuid4()) + '.jpg'
                img_name = os.getcwd() + os.sep + 'images' + os.sep + orig_name
                open(str(img_name), 'wb').write(response.content)
                break

        return orig_name,url,date_time
    # Grabs a users information
    # Inputs: Header
    # Ouputs: Dictionary with User's Information / "error" on Farmbot Error
    def user_info(self, headers):
        r = requests.get('https://my.farm.bot/api/users', headers=headers)

        if(r.status_code != 200):
            return "error"

        json_data = json.loads(r.content)

        return json_data[0]
    
    ###### Scheduler section ######

    # Get all the events placed
    def get_events(self, headers):
        r = requests.get('https://my.farm.bot/api/farm_events', headers=headers)
        if (r.status_code != 200):
            return False
        json_data = json.loads(r.content)
        if (len(json_data) == 0):
            return False
        return json_data
    
    # Get all the actions
    def get_sequences(self, headers):
        r = requests.get('https://my.farm.bot/api/sequences', headers=headers)
        if (r.status_code != 200):
            return False
        json_data = json.loads(r.content)
        if (len(json_data) == 0):
            return False
        return json_data
        
class Farmbot_handler:  
    def __init__(self, bot : Farmbot,x,y):
        now = datetime.datetime.now()
        print("Current hour: " + str(now.hour))
        if now.hour >= 17 or now.hour < 6:
            self.queue = ["LightON","Move","Capture","LightOFF"]
        else: 
             self.queue = ["Move","Capture"]

        print("Queue: " + str(self.queue))
        # Maintain a flag that lets us know if the bot is
        # ready for more commands.
        self.waiting_id = None
        self.busy = True
        self.bot = bot
        self.x = x
        self.y = y

    def try_next_job(self):
        if (len(self.queue) > 0) and (not self.busy) and self.waiting_id == None:
            command = self.queue.pop(0)
            self.busy = True
            if command == "LightON":
                print("LIGHT IS TURNING ON")
                id = self.bot.write_pin(7, 1)
                self.waiting_id = id
                return id
            
            if command == "Move":
                print("BOT IS MOVING TO LOCATION")
                id = self.bot.move_absolute(self.x,self.y,0)
                self.waiting_id = id
                return id
            
            if command == "Capture":
                print("BOT IS CAPTURING PHOTO")
                id = self.bot.take_photo()
                self.waiting_id = id
                return id
            
            if command == "LightOFF":
                id = self.bot.write_pin(7, 0)
                self.waiting_id = id
                return id
            
        if (len(self.queue) == 0 and self.waiting_id == None):
            print("Handler finished. Return False")
            return False

    def on_connect(self, bot, mqtt_client):
        print("Connected to bot!")
        self.bot.read_status()
        
    def on_change(self, bot, state):
        is_busy = state['informational_settings']['busy']
        if is_busy != self.busy:
            if is_busy:
                print("Device is busy")
            else:
                print("Device is idle")
        self.busy = is_busy
        self.try_next_job()

    def on_log(self, _bot, log):
        print("LOG: " + log['message'])

    def on_response(self, bot, response):
        if response.id == self.waiting_id:
            print(f"{response.id} completed.")
            self.waiting_id = None

    def on_error(self, _bot, response):
        print("ERROR: " + response.id)
        print("Reason(s) for failure: " + str(response.errors))
