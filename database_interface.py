from datetime import datetime, timedelta
from pytz import timezone

import sqlite3
import time
import os
import pandas as pd
import shutil

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job


class Database:
    # Handles the Database starting up
    # Inputs: Application Context
    def __init__(self, app):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        # Generates the database if it doesn't exists
        with app.open_resource("database.sql", mode="r") as f:
            cursor.executescript(f.read())

        connection.close()

    # Registers a User, or indicates that they are already in the system
    # Inputs: User's Email, User's API Key, Users's Token Timeout, User's Name, User's Location, Admin Accounts (if exists)
    # Outputs: True on Successful Registration / False on User Already Exists
    def register_user(
        self,
        user_email,
        user_token,
        token_timeout,
        name,
        location,
        farmbot_id,
        farmbot_name,
        adminAccounts=[],
    ):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        # Checks if User Exists
        cursor.execute("SELECT * FROM users where emailAddress = ?", (user_email,))
        data = cursor.fetchone()
        if data is not None:
            connection.close()
            print("User already exists")
            return False

        # Formats UNIX time to Date
        ts = int(token_timeout)
        date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")

        # Checks if User is Admin
        account_level = 0
        for email_text in adminAccounts:
            if email_text == user_email:
                account_level = 1

        # Merge Farmbot Info
        farmbot_info = (farmbot_id, farmbot_name, user_email)

        # Inserts User into Database
        cursor.execute(
            """INSERT INTO users (emailAddress, token, token_timeout, userType, name, location ) 
                        VALUES (?, ?, ?, ?, ?, ?)""",
            (user_email, user_token, date, account_level, name, location),
        )
        cursor.execute(
            "INSERT INTO farmbot (farmbotID, farmbotName, userEmail) VALUES (?, ?, ?)",
            (farmbot_info),
        )

        connection.commit()
        connection.close()
        return True

    # Refresh Token Timeout
    # Inputs: User's Email, User's API Key, User's Token timeout
    # Outputs: False on User is not in Database / True on Users is in Database
    def login_user(self, user_email, api_key, token_timeout):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        # Checks if User Exists
        cursor.execute("SELECT * FROM users where emailAddress = ?", (user_email,))
        data = cursor.fetchone()
        if data is None:
            connection.close()
            return False

        # Formats UNIX time to Date
        ts = int(token_timeout)
        date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")

        # Updates user's information
        cursor.execute(
            "UPDATE users SET token = ?, token_timeout = ? WHERE emailAddress = ?",
            (
                api_key,
                date,
                user_email,
            ),
        )
        connection.commit()
        connection.close()

        return True

    # Handles deletion of a User
    # Inputs: User's ID
    def delete_user(self, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        # Checks if User Exists
        check_sql = "SELECT * FROM users WHERE emailAddress = ?"
        cursor.execute(check_sql, (user_email,))

        # Deletes the User if they exist
        if cursor.fetchone() != None:
            sql = "DELETE FROM users WHERE emailAddress = ?"
            cursor.execute(sql, (user_email,))
            connection.commit()

            farmbot_sql = "SELECT farmbotID FROM farmbot WHERE userEmail = ?"
            cursor.execute(farmbot_sql, (user_email,))
            farmbot_data = cursor.fetchall()

            farmbot_sql = "DELETE FROM farmbot WHERE userEmail = ?"
            cursor.execute(farmbot_sql, (user_email,))
            connection.commit()

        connection.close()

    # Return a specific user via their API_KEY
    # Inputs: User's API Key
    # Outputs: User's Data
    def get_user(self, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM users WHERE emailAddress = ?", (user_email,))
        data = cursor.fetchone()

        return data

    # Finds API_key using email
    # Inputs: User's email
    # Outputs: User's API Key
    def find_key(self, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        cursor.execute("SELECT token FROM users WHERE emailAddress = ?", (user_email,))

        data = cursor.fetchone()

        return data[0]

    # Checks if an API Key is legitimate
    # Inputs: User's API Key, Current Time
    # Outputs: True on API Key Authenticated / False on API Key fails Authentication
    def user_check_token_exists(self, token, current_time):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        # Checks if API Key Exists
        cursor.execute("SELECT * FROM users WHERE token = ?", (token,))
        data = cursor.fetchone()

        # Checks if API Key is expired
        if data is not None:
            date = datetime.strptime(data[5], "%Y-%m-%d")
            if current_time < date.timestamp():
                return True
        return False

    # Checks if a User has Admin Priviledges
    # Inputs: User's API Key, User's Email
    # Outputs: True on User has privilege / False on Users lacks privilege
    def authenticate_user(self, token, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        if token != "":
            cursor.execute("SELECT * FROM users WHERE token = ?", (token,))
        else:
            cursor.execute("SELECT * FROM users WHERE emailAddress = ?", (user_email,))
        data = cursor.fetchone()

        if data is not None:
            if data[2] == "1":
                return True

        return False

    # Update User's privilege
    # Inputs: User's Email, User's Privilege
    def update_privilege(self, user_email, privilege):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE users SET userType = ? WHERE emailAddress = ?",
            (
                privilege,
                user_email,
            ),
        )
        connection.commit()
        connection.close()

    # Checks if a User's API Key & email are from the same User
    # Inputs: User's API Key, User's Email
    # Outputs: True on Same User / False on Different Users
    def check_same_user(self, token, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM users where token = ?", (token,))

        data = cursor.fetchone()

        if data is not None:
            if user_email == data[0]:
                return True

        return False

    # Handles how many users someone can see on /users
    # Inputs: User's API Key
    # Outputs: List of Users
    def user_table(self, api_key):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        # Grabs a Users data
        sql_query1 = "SELECT * FROM users WHERE token = ?"
        cursor.execute(sql_query1, (api_key,))
        data = cursor.fetchone()

        # Handles if a User is not Admin
        if data[2] != "1":
            data_array = [data]
            connection.close()
            return data_array

        # Grabs all of the users
        sql_query2 = "SELECT * FROM users"
        cursor.execute(sql_query2)

        data = cursor.fetchall()

        connection.close()

        return data

    # Gets all data from a certain table
    # Inputs: Table Name
    # Outputs: List of data on Success / False on Error
    def get_all(self, table):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql = "SELECT * FROM " + table

        cursor.execute(sql)

        data = cursor.fetchall()

        connection.close()

        if data is not None:
            return data

        return False

    # Checks if plant exists in Plants, and insert in if not
    # Inputs: Dictionary of Plant, User's API Key
    def add_unique_plant(self, plant, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        planted_date = datetime.fromisoformat(plant["plant_date"][:-1])
        plant_data = (
            plant["id"],
            plant["name"],
            planted_date,
            plant["x"],
            plant["y"],
            plant["device_id"],
            plant["openfarm_slug"],
        )
        sql_search = (
            """SELECT * FROM plants 
                        JOIN farmbot ON plants.farmbotID = farmbot.farmbotID
                        JOIN users ON farmbot.userEmail = users.emailAddress
                        WHERE userEmail = \'"""
            + user_email
            + "' AND plants.plantID = '"
            + str(plant_data[0])
            + "' "
        )

        cursor.execute(sql_search)
        data = cursor.fetchone()

        # Checks if plant already exists
        if data is not None:
            # print("Plant already exists")
            connection.close()
            return

        sql_create = "INSERT INTO plants (plantID, species, plantedDate, X, Y, farmbotID, openfarmSlug) VALUES (?, ?, ?, ?, ?, ?, ?)"

        cursor.execute(sql_create, plant_data)
        connection.commit()
        connection.close()
        return

    def get_group_plants(self, groupID):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql = "SELECT plants.plantID, plants.species FROM plants, plant_group_to_plant pgp WHERE plants.plantID = pgp.plantID AND pgp.groupID = ?"
        cursor.execute(sql, (groupID,))
        data = cursor.fetchall()
        connection.close()
        return data


    # Adds a weather to the database
    # Inputs: Weatherstack_Output, Location ID
    # Outputs: ID of inputted row
    def add_weather(self, weather_data, location):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        # Handles the timezone
        tz = timezone("Australia/Sydney")
        print("Location: ", location)

        now = datetime.now(tz).today().strftime("%Y-%m-%d %H:%M:%S")
        datenow = datetime.now(tz).today().strftime("%Y-%m-%d")

        # Formats the weather properly
        weather = (
            now,
            weather_data.name,
            weather_data.condition[0],
            weather_data.temp,
            weather_data.humidity,
            weather_data.windspeed,
            weather_data.precip,
            weather_data.cloudcover,
        )
        print("Weatherstack: ", weather)
        sql = """INSERT INTO weather(dateAndTime, location, weatherCondition, temperature, humidity, windSpeed, precip, cloudCover) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        cursor.execute(sql, weather)
        connection.commit()
        # Grabs the Row ID
        row_id = cursor.lastrowid
        connection.close()

        return row_id

    # Check if today's weather exists
    # Inputs: Location ID
    # Outputs: Weather ID
    def check_weather(self, location):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        # Handles the timezone
        tz = timezone("Australia/Sydney")
        print("Location: ", location)

        now = datetime.now(tz).today().strftime("%Y-%m-%d %H:%M:%S")
        datenow = datetime.now(tz).today().strftime("%Y-%m-%d %H")

        print("Date: ", datenow)
        # Checks if weather already exists for that day
        check_sql = (
            "SELECT * FROM weather WHERE location LIKE '"
            + location
            + "%' AND dateAndTime LIKE '"
            + datenow
            + "%'"
        )
        cursor.execute(check_sql)
        check = cursor.fetchone()
        if check is not None:
            print("Weather already exists")
            connection.close()
            return check[0]
        else:
            connection.close()
            return -1

    # Get a weather entry
    # Inputs: Weather ID
    # Outputs: Weather Data
    def get_weather(self, weather_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = "SELECT * FROM weather WHERE weatherID = ?"
        cursor.execute(sql, (weather_id,))
        data = cursor.fetchone()

        connection.close()

        return data

    # Grabs a Users Plants
    def get_farmbot(self, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql_query1 = """SELECT farmbotID, farmbotName FROM farmbot 
                        WHERE userEmail = ? 
                        ORDER BY farmbotID DESC"""

        cursor.execute(sql_query1, (user_email,))

        data = cursor.fetchall()

        return data

    # Grabs a Users Plants, but is Ordered by X & Y
    # Inputs: User's ID
    # Outputs: List of Plants
    def get_plant_ordered(self, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql_query1 = """SELECT * FROM plants 
                        JOIN farmbot ON plants.farmbotID = farmbot.farmbotID
                        JOIN users ON farmbot.userEmail = users.emailAddress
                        WHERE emailAddress = ? 
                        ORDER BY x ASC, y DESC"""

        cursor.execute(sql_query1, (user_email,))

        data = cursor.fetchall()

        return data

    # Grabs a Users Plants
    def get_plant_names(self, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql_query1 = """SELECT plantID, species FROM plants 
                        JOIN farmbot ON plants.farmbotID = farmbot.farmbotID
                        JOIN users ON farmbot.userEmail = users.emailAddress
                        WHERE emailAddress = ? 
                        ORDER BY species ASC"""

        cursor.execute(sql_query1, (user_email,))
        data = cursor.fetchall()
        return data

    def get_plantgroups(self, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql = "SELECT groupID, groupName FROM plantGroups WHERE userEmail = ?"
        cursor.execute(sql, (user_email,))
        data = cursor.fetchall()
        connection.close()
        return data

    def get_plant_openfarmslug(self, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql_query1 = """SELECT openfarmSlug FROM plants 
                        JOIN farmbot ON plants.farmbotID = farmbot.farmbotID
                        JOIN users ON farmbot.userEmail = users.emailAddress
                        WHERE emailAddress = ? 
                        ORDER BY species ASC"""
        cursor.execute(sql_query1, (user_email,))
        data = cursor.fetchall()
        return data
    
    def get_id_from_ofslug(self, ofslug):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql = "SELECT plantID FROM plants WHERE openfarmSlug = ?"
        cursor.execute(sql, (ofslug,))
        data = cursor.fetchone()
        connection.close()
        return data[0]
    
    def add_plant_group(self, user_email, groupID, groupName):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = "SELECT * FROM plantGroups WHERE groupID = ?"
        cursor.execute(sql, (groupID,))
        if cursor.fetchone() is not None:
            connection.close()
            return

        sql = "INSERT INTO plantGroups (groupID, groupName, userEmail) VALUES (?, ?, ?)"
        cursor.execute(sql, (groupID, groupName, user_email,))
        
        connection.commit()
        connection.close()

    def link_group_to_plants(self, groupID, plants):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        for p in plants:
          sql = "INSERT INTO plant_group_to_plant (plantID, groupID) VALUES (?, ?)"
          cursor.execute(sql, (p, groupID,))
        connection.commit()
        connection.close()

    def clear_group_tables(self, app):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql = "DROP TABLE IF EXISTS plant_group_to_plant"
        cursor.execute(sql)
        connection.commit()
        sql = "DROP TABLE IF EXISTS plantGroups"
        cursor.execute(sql)
        connection.commit()
        with app.open_resource("database.sql", mode="r") as f:
            cursor.executescript(f.read())
        connection.close()



    # Grabs a Users Plants
    def get_plant_data(self, user_email, plant_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql_query1 = """SELECT species,X,Y FROM plants 
                        JOIN farmbot ON plants.farmbotID = farmbot.farmbotID
                        JOIN users ON farmbot.userEmail = users.emailAddress
                        WHERE emailAddress = ? AND plantID = ?"""

        cursor.execute(sql_query1, (user_email, plant_id))

        data = cursor.fetchone()

        return data

    # Inserts plant entry into database
    # Inputs: Plant ID, Plant Data, Weather ID
    def plant_entry(self, plant_id, plant_data, weather_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = "INSERT INTO plantEntries (plantID, dateAndTime, R, G, B, leafArea, weatherID, leafCount, leafCircularity, leafSolidity, leafAspectRatio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"

        # Handles timezone
        tz = timezone("Australia/Sydney")
        date = datetime.now(tz).today().strftime("%Y-%m-%d %H:%M:%S")

        # Formats the Plants Data
        r = round(plant_data["color"]["r"], 0)
        g = round(plant_data["color"]["g"], 0)
        b = round(plant_data["color"]["b"], 0)

        # get leaf count
        leafCount = plant_data["leaf_count"]

        # get leaf circ
        leafCircularity = plant_data["leaf_circ"]
        
        # get leaf solid
        leafSolidity = plant_data["leaf_solid"]

        # get leaf aspect ratio
        leafAspectRatio = plant_data["leaf_aspect"]

        # Calculates the leaf area (1px = 0.026cm)
        # 1m2 = 10000cm2
        width = plant_data["width"] * 0.026
        height = plant_data["height"] * 0.026
        leafArea = round((width * height) / 10000, 3)

        plant_object = (plant_id, date, r, g, b, leafArea, weather_id, leafCount, leafCircularity, leafSolidity, leafAspectRatio)

        cursor.execute(sql, plant_object)
        connection.commit()
        connection.close()

    # Get the entry based on id
    # Inputs: EntryID
    def get_entry_direct(self, entry_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = """SELECT plantEntries.*, species, X, Y FROM plantEntries 
                JOIN plants ON plantEntries.plantID = plants.plantID
                WHERE plantEntries.entryID = ?"""

        cursor.execute(sql, (entry_id,))
        data = cursor.fetchone()
        connection.close()

        return data
    
        # Get the entry based on id
    # Inputs: EntryID
    def get_entry_direct_full(self, entry_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = """SELECT plantEntries.*, species, weatherCondition,temperature, X, Y FROM plantEntries 
                JOIN plants ON plantEntries.plantID = plants.plantID
                JOIN weather ON plantEntries.weatherID = weather.weatherID
                WHERE plantEntries.entryID = ?"""

        cursor.execute(sql, (entry_id,))
        data = cursor.fetchone()
        connection.close()

        return data

    # Get the entry based on id
    # Inputs: EntryID
    def get_entry_direct(self, entry_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = """SELECT plantEntries.*, species, X, Y FROM plantEntries 
                JOIN plants ON plantEntries.plantID = plants.plantID
                WHERE plantEntries.entryID = ?"""

        cursor.execute(sql, (entry_id,))
        data = cursor.fetchone()
        connection.close()

        return data

    # Get the newest plant entry of a plant
    # Inputs: Plant ID
    def get_entry_latest(self, plant_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = """SELECT plantEntries.*, species, X, Y FROM plantEntries 
                JOIN plants ON plantEntries.plantID = plants.plantID
                WHERE plantEntries.plantID = ? ORDER BY dateAndTime DESC LIMIT 1"""

        cursor.execute(sql, (plant_id,))
        data = cursor.fetchone()
        connection.close()

        return data

    # Get all plant entry of a plant
    # Inputs: Plant ID
    def get_entry_plant_all(self, plant_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = """SELECT plantEntries.*, species, weatherCondition,temperature, X, Y FROM plantEntries 
                JOIN plants ON plantEntries.plantID = plants.plantID
                JOIN weather ON plantEntries.weatherID = weather.weatherID
                WHERE plantEntries.plantID = ? ORDER BY plantEntries.dateAndTime DESC"""

        cursor.execute(sql, (plant_id,))
        data = cursor.fetchall()
        connection.close()

        return data

    # Get the plant entry of a plant within range
    # Inputs: Plant ID, Start Date, End Date
    def get_entry_range(self, plant_id, start_date, end_date):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = """SELECT plantEntries.*, species, weatherCondition,temperature FROM plantEntries
                JOIN plants ON plantEntries.plantID = plants.plantID 
                JOIN weather ON plantEntries.weatherID = weather.weatherID
                WHERE plantEntries.plantID = ? AND date(plantEntries.dateAndTime) BETWEEN ? AND ?"""

        cursor.execute(sql, (plant_id, start_date, end_date))
        data = cursor.fetchall()
        connection.close()

        return data

    # Get the plant entry of all plant within range
    # Inputs: Start Date, End Date
    def get_entry_range_all(self, user_email, start_date, end_date):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = """SELECT plantEntries.*, species, weatherCondition,temperature FROM plantEntries
                JOIN plants ON plantEntries.plantID = plants.plantID
                JOIN farmbot ON plants.farmbotID = farmbot.farmbotID
                JOIN users ON farmbot.userEmail = users.emailAddress 
                JOIN weather ON plantEntries.weatherID = weather.weatherID
                WHERE emailAddress = ? AND date(plantEntries.dateAndTime) BETWEEN ? AND ?"""

        cursor.execute(sql, (user_email, start_date, end_date))
        cursor.execute(sql, (user_email, start_date, end_date))
        data = cursor.fetchall()
        connection.close()

        return data

    # Get the plant entry of all plant
    def get_entry_all(self, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = """SELECT plantEntries.*, species, weatherCondition,temperature FROM plantEntries
                JOIN plants ON plantEntries.plantID = plants.plantID
                JOIN farmbot ON plants.farmbotID = farmbot.farmbotID
                JOIN users ON farmbot.userEmail = users.emailAddress
                JOIN weather ON plantEntries.weatherID = weather.weatherID
                WHERE emailAddress = ?"""

        cursor.execute(sql, (user_email,))
        data = cursor.fetchall()
        connection.close()

        return data

    # Inserts phtoto URL into database
    # Inputs: EntryID, Photo URL, Date
    def photo_entry(self, entry_id, url, entry_date):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = "INSERT INTO picturesOfPlants (entryID, photoURL, dateAndTime) VALUES (?, ?, ?)"

        cursor.execute(sql, (entry_id, url, entry_date))
        connection.commit()
        connection.close()

    # Grabs image url
    # Inputs: Entry ID
    # Outputs: Image URL
    def get_image(self, entry_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = "SELECT * FROM picturesOfPlants WHERE entryID = ?"

        cursor.execute(sql, (entry_id,))
        data = cursor.fetchall()
        connection.close()

        return data

    # Delete Entry
    # Inputs: Entry ID
    def delete_entry(self, entry_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = "DELETE FROM plantEntries WHERE entryID = ?"

        cursor.execute(sql, (entry_id,))
        connection.commit()
        connection.close()

    # Delete Image
    # Inputs: Entry ID
    def delete_image(self, entry_id):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = "DELETE FROM picturesOfPlants WHERE entryID = ?"

        cursor.execute(sql, (entry_id,))
        connection.commit()
        connection.close()

    # Export Data
    # Inputs: Plant ID, Start Date, End Date
    # Outputs: Dataframe
    def export_data(self, plant_id, start_date, end_date):
        connection = sqlite3.connect("database.db")

        if start_date == "" or end_date == "":
            if plant_id == "-1":
                sql = """SELECT plantEntries.*, species, weatherCondition,temperature FROM plantEntries
                        JOIN plants ON plantEntries.plantID = plants.plantID
                        JOIN weather ON plantEntries.weatherID = weather.weatherID"""
            else:
                sql = (
                    """SELECT plantEntries.*, species, weatherCondition,temperature FROM plantEntries
                        JOIN plants ON plantEntries.plantID = plants.plantID
                        JOIN weather ON plantEntries.weatherID = weather.weatherID 
                        WHERE plantEntries.plantID = """
                    + plant_id
                )
        else:
            if plant_id == "-1":
                sql = (
                    """SELECT plantEntries.*, species, weatherCondition,temperature FROM plantEntries
                        JOIN plants ON plantEntries.plantID = plants.plantID
                        JOIN weather ON plantEntries.weatherID = weather.weatherID 
                        WHERE date(plantEntries.dateAndTime) BETWEEN """
                    + start_date
                    + """ AND """
                    + end_date
                )
            else:
                sql = """SELECT plantEntries.*, species, weatherCondition,temperature FROM plantEntries
                        JOIN plants ON plantEntries.plantID = plants.plantID
                        JOIN weather ON plantEntries.weatherID = weather.weatherID 
                        WHERE plantEntries.plantID = """
                sql = (
                    sql
                    + plant_id
                    + """ AND date(plantEntries.dateAndTime) BETWEEN """
                    + start_date
                    + """ AND """
                    + end_date
                )

        df = pd.read_sql(sql, connection)
        return df

    def add_schedule(self, plantid, sdate, options_str, description, user_email):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql_create = "INSERT INTO schedules (schedulePlantID, scheduleStartDate, scheduleRepeats, scheduleDescription, scheduleEmail) VALUES (?, ?, ?, ?, ?)"
        try:
            cursor.execute(
                sql_create,
                (plantid, sdate, options_str, description, user_email,),
            )
        except sqlite3.Error as e:
            print("SQLite error:", e)

        connection.commit()
        connection.close()

    def delete_schedule(self, scheduleID):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        sql = "DELETE FROM schedules WHERE scheduleID = ?"

        cursor.execute(sql, (scheduleID,))
        connection.commit()
        connection.close()

    def create_schedule_jobs(self, scheduler: BackgroundScheduler, job_function):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM schedules")
        schedules = cursor.fetchall()
        cursor.close()

        for row in schedules:
            scheduleID, schedulePlantID, scheduleStartDate, scheduleRepeats, scheduleDescription, scheduleEmail = row

            schedule_start_datetime = datetime.strptime(scheduleStartDate, "%Y-%m-%d %H:%M:%S")

            if scheduleRepeats == 'none':
                j: Job = scheduler.add_job(job_function, args=(scheduleID, schedulePlantID, scheduleEmail), trigger=DateTrigger(run_date=schedule_start_datetime))
                print(f"Created new schedule job for [{j.args}] {j.id} - {j.trigger}")
            elif scheduleRepeats == 'daily':
                cron = f"{schedule_start_datetime.minute} {schedule_start_datetime.hour} * * *"
                j: Job = scheduler.add_job(job_function, args=(scheduleID, schedulePlantID, scheduleEmail),
                                           trigger=CronTrigger.from_crontab(cron))
                print(f"Created new daily schedule job for [{j.args}] {j.id} - {j.trigger} --- {j.next_run_time}")
            elif scheduleRepeats == 'weekly':
                cron = f"{schedule_start_datetime.minute} {schedule_start_datetime.hour} * * {schedule_start_datetime.weekday()}" # sun == 6 mon == 0
                j: Job = scheduler.add_job(job_function, args=(scheduleID, schedulePlantID, scheduleEmail),
                                           trigger=CronTrigger.from_crontab(cron))
                print(f"Created new weekly schedule job for [{j.args}] {j.id} - {j.trigger} --- {j.next_run_time}")
            elif scheduleRepeats == 'monthly':
                cron = f"{schedule_start_datetime.minute} {schedule_start_datetime.hour} {schedule_start_datetime.day} * *" # sun == 6 mon == 0
                j: Job = scheduler.add_job(job_function, args=(scheduleID, schedulePlantID, scheduleEmail),
                                           trigger=CronTrigger.from_crontab(cron))
                print(f"Created new monthly schedule job for [{j.args}] {j.id} - {j.trigger} --- {j.next_run_time}")

    def link_aiart_to_entry(self, artID, entryID):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql = "INSERT INTO aiart_to_entry (artID, entryID) VALUES (?, ?)"
        cursor.execute(sql, (artID, entryID,))
        connection.commit()
        connection.close()

    def save_ai_filepath(self, user_prompt, posPrompt, negPrompt, filepath, datatypes, seed):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql = "INSERT INTO aiArt (artPrompt, artPosPrompt, artNegPrompt, artFilePath, artDate, artDataTypes, seed) VALUES (?, ?, ?, ?, ?, ?, ?)"
        tz = timezone("Australia/Sydney")
        now = datetime.now(tz).today().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(sql, (user_prompt, posPrompt, negPrompt, filepath, now, ', '.join(datatypes), seed))
        id = cursor.lastrowid
        connection.commit()
        connection.close()
        return id
    
    def get_art_by_id(self, artID):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql = "SELECT * FROM aiArt WHERE artID = ?"
        cursor.execute(sql, (artID,))
        data = cursor.fetchone()
        connection.close()
        return data

    def get_art_entry_row_data(self, artID):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        sql = "SELECT * FROM aiart_to_entry ate, plantEntries pe WHERE pe.entryID = ate.entryID AND artID = ?"
        cursor.execute(sql, (artID,))
        data = cursor.fetchall()
        connection.close()
        return data

    def get_art_entry_by_type(self, dataTypes: list[str]):
        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()
        types = ', '.join(dataTypes)
        sql = "SELECT * FROM aiArt WHERE artDataTypes = ?"
        cursor.execute(sql, (types,))
        data = cursor.fetchall()
        connection.close()
        return data