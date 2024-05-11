from flask import (
    Flask,
    request,
    render_template,
    redirect,
    session,
    make_response,
    url_for,
    g,
    send_from_directory,
    send_file
)
from waitress import serve

from tqdm import tqdm
from datetime import datetime

from database_interface import Database
from farmbot_interface import Farmbot_api
from farmbot_interface import Farmbot_handler
from plantcv_interface import plantcv_interface
from weatherstack_interface import Weatherstack
from farmbot import Farmbot, FarmbotToken
from time import sleep

# scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

scheduler: BackgroundScheduler

# ai
from ai_interface import AI

import zipfile


import requests
import json
import time
import atexit
import os
import datetime
import threading
import shutil

# PORT = 5003
PORT = 80

app = Flask(__name__)

# Make the WSGI interface available at the top level so wfastcgi can get it.
wsgi_app = app.wsgi_app

# Grabs keys out of config file
config = open(
    "config.json",
)
api_keys = json.load(config)
config.close()

# Handles if Weatherstack key is missing
if (
    "weatherstack" not in api_keys
    or api_keys["weatherstack"] == ""
    or api_keys["weatherstack"] is None
):
    print("WeatherStack API key is mssing. Please insert the key into the JSON file!")
    exit(0)

# Handles if Admin accounts are missing
if "admin-accounts" not in api_keys:
    print(
        "Admin accounts is missing. Please declare an admin into the config.json file"
    )
    exit(0)

# Handles if save-images flag (PlantCV output mode) is missing or empty
if (
    "save-images" not in api_keys
    or api_keys["save-images"] == ""
    or api_keys["save-images"] is None
):
    print("Save-Images option is missing. Please insert this into the config.json file")
    exit(0)

adminAccounts = api_keys["admin-accounts"].split(",")
img_flag = api_keys["save-images"]

database = Database(app)
farmbot_api = Farmbot_api()
weatherstack = Weatherstack(api_keys["weatherstack"])
ai = AI()

credentials = []


####################################################################
@app.route("/", methods=["POST", "GET"])
def login():
    # Checks if cookie exists
    if request.cookies.get("token") is not None:
        if database.user_check_token_exists("token", time.time()):
            return redirect(url_for("/dashboard"))

    # Checks if not POST request
    if request.method == "GET":
        return render_template("login.html", data=str(PORT), error=0)

    login = request.form

    # Handles if a user POST requests with no data
    if "email" not in login or "password" not in login:
        return render_template("login.html", data=str(PORT), error=-1)

    # Create the global credentials variable
    credentials.clear()
    credentials.append(login["email"])
    credentials.append(login["password"])

    # create schedules when user logged in
    if len(scheduler.get_jobs()) == 0:
        database.create_schedule_jobs(scheduler, capture_plant_job)

    api_key = farmbot_api.user_account(credentials[0], credentials[1])

    if api_key == -1:
        return render_template("login.html", data=str(PORT), error=-2)

    if api_key == 0:
        return render_template("login.html", data=str(PORT), error=-3)

    headers = {"Authorization": "Bearer " + api_key[0]}

    user_info = farmbot_api.user_info(headers)

    # Checks if the account exists in local database
    account_exists = database.login_user(user_info["email"], api_key[0], api_key[1])
    if account_exists == False:
        return render_template("login.html", data=str(PORT), error=-4)

    # Generates the response with a Cookie & timelimit on Cookie
    response = make_response(redirect(url_for("dashboard")))
    response.set_cookie("token", api_key[0], max_age=(api_key[1] - time.time()))

    return response


################################################################################################
# Dashboard Endpoint
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    api_key = request.cookies.get("token")

    # Handles if no cookie is available or cookie is incorrect
    if (
        api_key is None
        or not database.user_check_token_exists(api_key, time.time())
        or len(credentials) == 0
    ):
        return redirect(url_for("login"))

    # Refresh the database
    update_database(credentials[0])
    print("db updated")

    # Grab the list of bots
    bot_list = database.get_farmbot(credentials[0])

    # Go to Dashboard
    return render_template("dashboard.html", title="Plant Data", bots=bot_list)


################################################################################################
# Capture Data Endpoint
@app.route("/capture-data", methods=["POST", "GET"])
def capture_data():
    api_key = request.cookies.get("token")

    # Handles if no cookie is available or cookie is incorrect
    if (
        api_key is None
        or not database.user_check_token_exists(api_key, time.time())
        or len(credentials) == 0
    ):
        return redirect(url_for("login"))
    plant_list = database.get_plant_names(credentials[0])

    form = request.form
    if "plantid" in form:
        user = database.get_user(credentials[0])
        location = user[3]
        weatherID = get_weather(location)
        plant_id = form["plantid"]

        capture_plant(plant_id, weatherID)

        plant_data = database.get_entry_latest(plant_id)
        # Grab weather Data from database
        weather_data = database.get_weather(weatherID)
        # Grab URL from database
        url = database.get_image(plant_data[0])
        return render_template(
            "capture-data.html",
            title="Capture Data",
            plantID=plant_id,
            url=url[0][2],
            plants=plant_list,
            data=plant_data,
            weather=weather_data,
        )

    return render_template(
        "capture-data.html", title="Capture Data", plants=plant_list, plantID=0
    )


################################################################################################
# Report Endpoint
@app.route("/report", methods=["POST", "GET"])
def report():
    api_key = request.cookies.get("token")

    # Handles if no cookie is available or cookie is incorrect
    if (
        api_key is None
        or not database.user_check_token_exists(api_key, time.time())
        or len(credentials) == 0
    ):
        return redirect(url_for("login"))

    plant_list = database.get_plant_names(credentials[0])
    form = request.form

    # ai art section
    if "art" in form:
        if "selectedPlant[]" in form:
            selected_plants = form.getlist("selectedPlant[]")
            return redirect(url_for("art", id=",".join(selected_plants)))

    if "plantid" in form:
        plant_id = form["plantid"]
        url = []
        start_date = form["startdate"]
        end_date = form["enddate"]
        if "display" in form:
            display = form["display"]
        else:
            display = "False"
        # Handles if no date is selected
        if start_date == "" or end_date == "":
            if plant_id == "-1":
                entries = database.get_entry_all(credentials[0])
            else:
                entries = database.get_entry_plant_all(plant_id)

            if "export" in form:
                df = database.export_data(plant_id, start_date, end_date)
                if df is None:
                    return render_template(
                        "report.html",
                        title="Report",
                        plantID=plant_id,
                        photo=display,
                        url=url,
                        plants=plant_list,
                        entries=entries,
                        error=-2,
                    )

                df["leafCircularity"] = (df["leafCircularity"] * 100).apply(
                    lambda x: f"{x:.2f}%"
                )
                df["leafSolidity"] = (df["leafSolidity"] * 100).apply(
                    lambda x: f"{x:.2f}%"
                )
                df["leafAspectRatio"] = (df["leafAspectRatio"]).apply(
                    lambda x: f"{x:.2f}%"
                )

                csv = df.to_csv(index=False)
                response = make_response(csv)
                cd = "attachment; filename=mycsv.csv"
                response.headers["Content-Disposition"] = cd
                response.mimetype = "text/csv"
                return response

            for entry in entries:
                url_pair = database.get_image(entry[0])
                if len(url_pair) == 2:
                    url.append((url_pair[0][2], url_pair[1][2], "Unavailable"))
                elif len(url_pair) == 3:
                    url.append((url_pair[0][2], url_pair[1][2], url_pair[2][2]))
                else:
                    url.append((url_pair[0][2], "Unavailable", "Unavailable"))
            # for fixing weather data being shown
            for i, entry in enumerate(entries):
                # Fetch weather data based on the entry's weatherID from the "weather" table
                weather_data = database.get_weather(
                    entry[0]
                )  # Assuming entry[0] is the weatherID
                # print(weather_data)
                if weather_data:
                    entry_weather_condition = weather_data[
                        2
                    ]  # Assuming weather_data[2] is the Weather Condition
                    entry_temperature = weather_data[
                        3
                    ]  # Assuming weather_data[3] is the Temperature
                else:
                    entry_weather_condition = "N/A"
                    entry_temperature = "N/A"

                # Convert the tuple to a list for modification
                entry_list = list(entry)

                # Append weather-related data to the list
                entry_list.append(entry_weather_condition)
                entry_list.append(entry_temperature)

                # Convert the list back to a tuple
                entries[i] = tuple(entry_list)

            return render_template(
                "report.html",
                title="Report",
                plantID=plant_id,
                photo=display,
                url=url,
                plants=plant_list,
                entries=entries,
            )

        # Grab entries from database
        if plant_id == "-1":
            entries = database.get_entry_range_all(credentials[0], start_date, end_date)
        else:
            entries = database.get_entry_range(plant_id, start_date, end_date)

        if "export" in form:
            df = database.export_data(plant_id, start_date, end_date)
            if df is None:
                return render_template(
                    "report.html",
                    title="Report",
                    plantID=plant_id,
                    photo=display,
                    url=url,
                    plants=plant_list,
                    entries=entries,
                    error=-2,
                )
            csv = df.to_csv(index=False)
            response = make_response(csv)
            cd = "attachment; filename=mycsv.csv"
            response.headers["Content-Disposition"] = cd
            response.mimetype = "text/csv"
            return response
        # Grab photos from database
        for entry in entries:
            url_pair = database.get_image(entry[0])
            if len(url_pair) == 2:
                url.append((url_pair[0][2], url_pair[1][2], "Unavailable"))
            elif len(url_pair) == 3:
                url.append((url_pair[0][2], url_pair[1][2], url_pair[2][2]))
            else:
                url.append((url_pair[0][2], "Unavailable", "Unavailable"))

        return render_template(
            "report.html",
            title="Report",
            plantID=plant_id,
            photo=display,
            url=url,
            plants=plant_list,
            entries=entries,
        )

    # Go to report
    return render_template("report.html", title="Report", plants=plant_list, plantID=0)


################################################################################################
# Garden Explorer Endpoint
@app.route("/garden-explorer", methods=["POST", "GET"])
def garden_explorer():
    api_key = request.cookies.get("token")

    # Handles if no cookie is available or cookie is incorrect
    if (
        api_key is None
        or not database.user_check_token_exists(api_key, time.time())
        or len(credentials) == 0
    ):
        return redirect(url_for("login"))

    plant_list = database.get_plant_names(credentials[0])
    form = request.form
    # Delete Entry
    if "delete" in form:
        entry_id = form["delete"]
        print("Delete Entry: ", entry_id)
        entry_data = database.get_entry_direct(entry_id)
        plant_id = entry_data[1]
        img = database.get_image(entry_id)

        # Get the folder name from green_detection path
        output_folder = str(img[1][2])[:-16]
        folder_path = str(os.getcwd() + output_folder)

        # Delete the entry
        database.delete_entry(entry_id)
        # Delete the image data
        database.delete_image(entry_id)
        # Delete the folder
        shutil.rmtree(folder_path)

        return render_template(
            "garden-explorer.html",
            title="Garden Explorer",
            plantID=0,
            entryID=0,
            plants=plant_list,
        )

    # Show Entry's Details
    if "entryid" in form:
        entry_id = form["entryid"]
        print("Entry ID: ", entry_id)
        url = []
        entry_data = database.get_entry_direct(entry_id)
        plant_id = entry_data[1]
        url_pair = database.get_image(entry_data[0])
        if len(url_pair) == 2:
            url.append(url_pair[1][2])
            url.append("Unavailable")
        elif len(url_pair) == 3:
            url.append(url_pair[1][2])
            url.append(url_pair[2][2])
        else:
            url.append("Unavailable")
            url.append("Unavailable")
        return render_template(
            "garden-explorer.html",
            title="Garden Explorer",
            plantID=0,
            url=url,
            plants=plant_list,
            entryID=entry_id,
            data=entry_data,
        )

    # Show Entries
    if "plantid" in form:
        plant_id = form["plantid"]
        print("plant id: ", plant_id)
        start_date = form["startdate"]
        print("start date: ", start_date)
        # Grab all entries of plant
        if start_date == "":
            if plant_id == "-1":
                entries = database.get_entry_all(credentials[0])
            else:
                entries = database.get_entry_plant_all(plant_id)
        # Grab entries for the date
        elif start_date != "":
            if plant_id == "-1":
                entries = database.get_entry_range_all(
                    credentials[0], start_date, start_date
                )
            else:
                entries = database.get_entry_range(plant_id, start_date, start_date)

        return render_template(
            "garden-explorer.html",
            title="Garden Explorer",
            plantID=plant_id,
            entryID=0,
            plants=plant_list,
            entries=entries,
        )

    # Default Route
    return render_template(
        "garden-explorer.html",
        title="Garden Explorer",
        plants=plant_list,
        plantID=0,
        entryID=0,
    )


################################################################################################
# Users Endpoint
@app.route("/users", methods=["GET", "POST"])
def users():
    api_key = request.cookies.get("token")

    # Checks if the api_key is present
    if api_key is None or not database.user_check_token_exists(api_key, time.time()):
        return redirect(url_for("login"))

    # Checks if user is actually sending data
    if request.method != "POST":
        user_table = database.user_table(api_key)
        if database.authenticate_user(api_key, "") == False:
            admin = 0
        else:
            admin = 1
        return render_template(
            "users.html", admin=admin, value=user_table, title="Users"
        )

    # Authenticates that the user's supplied api_key to an Admin
    if database.authenticate_user(api_key, "") == False:
        user_table = database.user_table(api_key)
        print("Not an admin")
        return render_template("users.html", admin=0, value=user_table, title="Users")
    else:
        admin = 1

    # Recieves the sent data
    data = request.form
    # Checks if the necessary items were in the data
    if "user" not in data:
        user_table = database.user_table(api_key)
        return render_template(
            "users.html", admin=admin, value=user_table, title="Users"
        )

    # Grabs the necessary items
    user = data["user"]
    action = data["action"]
    print(user, action)

    if action == "delete":
        database.delete_user(user)
    else:
        # Loads the config file
        with open("config.json", "r") as f:
            config = json.load(f)

        # Promotes or demotes the user
        if database.authenticate_user("", user) == False:
            config["admin-accounts"] += "," + user
            database.update_privilege(user, 1)
        else:
            config["admin-accounts"] = config["admin-accounts"].replace("," + user, "")
            database.update_privilege(user, 0)

        # Saves the config file
        with open("config.json", "w") as f:
            json.dump(config, f)

    # Handles if it is the same user
    if database.check_same_user(api_key, user):
        response = make_response(redirect(url_for("login")))
        response.delete_cookie("token")
        return response

    # Else route to default page
    user_table = database.user_table(api_key)
    return render_template("users.html", admin=admin, value=user_table, title="Users")


################################################################################################
# User Registration Endpoint
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template(
            "register.html", title="User Registration", port=PORT, error=0
        )

    # Grabs info received from POST request
    data = request.form

    # Checks if GET request or missing vital data
    if "email" not in data or "password" not in data or "location" not in data:
        return render_template("register.html", title="User Registration", error=-1)

    # Grabs the API Key From farmbot
    api_key = farmbot_api.user_account(data["email"], data["password"])

    location = data["location"]
    weatherstack_data = weatherstack.current(location)
    location = weatherstack_data.name

    if api_key == -1:
        return render_template("register.html", title="User Registration", error=-2)

    if api_key == 0:
        return render_template("register.html", title="User Registration", error=-3)

    if weatherstack.validate_location(location) == -1:
        return render_template("register.html", title="User Registration", error=-5)

    headers = {"Authorization": "Bearer " + api_key[0]}

    user_info = farmbot_api.user_info(headers)
    farmbot_info = farmbot_api.farmbot_info(headers)

    # Registers if user exists, or errors out if account already linked
    user_exists = database.register_user(
        user_info["email"],
        api_key[0],
        api_key[1],
        user_info["name"],
        location,
        farmbot_info["id"],
        farmbot_info["name"],
        adminAccounts,
    )

    if user_exists == False:
        return render_template("register.html", title="User Registration", error=-4)

    response = make_response(redirect(url_for("login")))
    response.set_cookie("token", api_key[0], max_age=(api_key[1] - time.time()))
    return response


################################################################################################
# Handles Javascript files
@app.route("/scripts/<path:path>", methods=["GET"])
def send_js(path):
    return send_from_directory("scripts", path, mimetype="text/javascript")


################################################################################################
# Handles Images
@app.route("/images/<path:path>", methods=["GET"])
def send_img(path):
    try:
        return send_from_directory("images", path)
    except:
        return ""


@app.route("/ai_images/<path:path>", methods=["GET"])
def send_ai_img(path):
    try:
        return send_from_directory("ai_images", path)
    except:
        return ""


################################################################################################
# Logout Endpoint
@app.route("/logout")
def cookie():
    # credentials.clear()
    response = make_response(redirect(url_for("login")))
    response.delete_cookie("token")
    return response


################################################################################################
# Schedule
@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    api_key = request.cookies.get("token")
    # Handles if no cookie is available or cookie is incorrect
    if (
        api_key is None
        or not database.user_check_token_exists(api_key, time.time())
        or len(credentials) == 0
    ):
        return redirect(url_for("login"))

    token = database.find_key(credentials[0])

    headers = {"Authorization": "Bearer " + token}

    form = request.form

    plant_list = database.get_plant_names(credentials[0])
    group_list = database.get_plantgroups(credentials[0])

    #### CREATE SCHEDULE
    # go to schedule creation page
    if "create_schedule" in form:
        return render_template(
            "schedule.html",
            title="Create Schedule",
            create_schedule=1,
            plants=plant_list,
            groups=group_list,
            error=0,
        )

    # delete a schedule
    if "delete_schedule" in form:
        scheduleID = int(form["delete_schedule"])
        print(f"Going to delete scheduleID {scheduleID}")
        database.delete_schedule(scheduleID)
        scheduler.remove_all_jobs()  # remove all current jobs
        database.create_schedule_jobs(scheduler, capture_plant_job)  # create new jobs

    # submit a new schedule
    if (
        "create_new_schedule" in request.form
        and request.form["create_new_schedule"] == "Create New Schedule"
    ):
        plantid = request.form["plantid"]  # plant id
        groupid = request.form["plantgroupid"]  # group id
        s_date = request.form["startdate"]  # schedule start date
        repeats_option = request.form["repeats"]  # none,daily,weekly,monthly
        description = request.form["description"][
            :100
        ]  # schedule description with 100 char limit

        if plantid == "-1" and groupid == "-1":
            return render_template(
                "schedule.html",
                title="Create Schedule",
                create_schedule=1,
                plants=plant_list,
                groups=group_list,
                error=1,
            )

        print(f"plantid: {plantid} | groupid: {groupid}")

        datetime_object = datetime.datetime.fromisoformat(s_date).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        existing_schedules = database.get_all("schedules")

        for existing_schedule in existing_schedules:
            existing_datetime_str = existing_schedule[
                2
            ]  # Assuming existing_schedule[2] is a datetime string
            try:
                existing_datetime = datetime.datetime.fromisoformat(
                    existing_datetime_str
                )
                datetime_object_obj = datetime.datetime.fromisoformat(s_date)
                if abs(datetime_object_obj - existing_datetime) < datetime.timedelta(
                    minutes=2
                ):
                    # If the time difference is less than 5 minutes, it's a clash
                    print("Schedule clash. Please choose a different time.")
                    return render_template(
                        "schedule.html",
                        title="Create Schedule",
                        create_schedule=1,
                        plants=plant_list,
                        groups=group_list,
                        error=2,
                    )
            except ValueError:
                # Handle the case where existing_datetime_str is not a valid datetime string
                print("Invalid datetime format in existing schedule.")

        # a group is selected
        if plantid == "-1" and groupid != "-1":
            plants = database.get_group_plants(groupid)
            current_s_date = datetime.datetime.fromisoformat(s_date)
            for p in plants:
                print(f"PlantID: {p[0]}, Name: {p[1]}, Time: {current_s_date}")
                plantid = p[0]
                plantname = p[1]
                database.add_schedule(
                    plantid,
                    current_s_date.strftime("%Y-%m-%d %H:%M:%S"),
                    repeats_option,
                    description,
                    credentials[0],
                )
                current_s_date = current_s_date + datetime.timedelta(minutes=2)
            scheduler.remove_all_jobs()  # remove all current jobs
            database.create_schedule_jobs(
                scheduler, capture_plant_job
            )  # create the new schedule job
        else:
            database.add_schedule(
                plantid, datetime_object, repeats_option, description, credentials[0]
            )  # add to db
            scheduler.remove_all_jobs()  # remove all current jobs
            database.create_schedule_jobs(
                scheduler, capture_plant_job
            )  # create the new schedule job

    schedules = database.get_all("schedules")

    ### Get the plants name using the id from the schedules table
    schedules_plants = {}
    for s in schedules:
        pid = s[
            1
        ]  # plant id TODO Change this if u update something in the schedules table
        pd = database.get_plant_data(credentials[0], pid)
        schedules_plants[pid] = pd[0]  # get the species/name of plant

    #### VIEW SCHEDULE
    # This is called when a user clicks on the ID of a schedule
    if "schedule_id" in form:
        sid = int(form["schedule_id"])  # schedule id
        schedule_data = list(filter(lambda x: int(x[0]) == sid, schedules))[0]
        return render_template(
            "schedule.html",
            title="View Schedule",
            view_schedule=sid,
            schedules_plants=schedules_plants,
            schedule_data=schedule_data,
            error=0,
        )

    return render_template(
        "schedule.html",
        title="Schedule",
        schedules=schedules,
        schedules_plants=schedules_plants,
        error=0,
    )


################################################################################################
# Art
@app.route("/art", methods=["GET", "POST"])
def art():
    api_key = request.cookies.get("token")
    # Handles if no cookie is available or cookie is incorrect
    if (
        api_key is None
        or not database.user_check_token_exists(api_key, time.time())
        or len(credentials) == 0
    ):
        return redirect(url_for("login"))

    plantids = request.args.get("id", "").split(",")

    # check if query string is just numbers
    check = any(s.isnumeric() for s in plantids)
    if len(plantids) == 0 or "" in plantids or not check:
        return redirect(url_for("report"))

    entries = []
    for id in plantids:
        entries.append(database.get_entry_direct_full(id))

    if len(entries) == 0 or None in entries:
        return redirect(url_for("report"))

    # generate art button has been pressed
    if "art" in request.form:
        selectedDataTypes = request.form.getlist("selectedTypes[]")

        posPrompt = request.form["posPrompt"]
        negPrompt = request.form["negPrompt"]
        img_seed = request.form["imgSeed"]
        print("input from html: ", img_seed)
        print(type(img_seed))

        user_prompt = posPrompt + ":" + negPrompt

        artpath, final_prompt, seed = ai.generate_art(
            user_prompt, entries, selectedDataTypes, database, img_seed
        )
        id = database.save_ai_filepath(final_prompt, posPrompt, negPrompt, artpath, selectedDataTypes, str(seed))

        for i in entries:
            database.link_aiart_to_entry(id, i[0])

        return render_template(
            "art.html",
            title="Art",
            entries=entries,
            posPrompt=posPrompt,
            negPrompt=negPrompt,
            final_prompt=final_prompt,
            selectedtypes=selectedDataTypes,
            seed=seed,
            artpath=artpath,
        )

    return render_template("art.html", title="Art", entries=entries)


################################################################################################
@app.route("/art-entries", methods=["GET", "POST"])
def artEntries():
    
    if "filter" in request.form:
        selectedDataTypes = request.form.getlist("selectedTypes[]")
        entries = database.get_art_entry_by_type(selectedDataTypes)
        pEntries = [] # pEntries is the plant report entry id (the row id of Report)
        for entry in entries:
          entryRow = database.get_art_entry_row_data(entry[0])
          t = []
          for e in entryRow:
            t.append(e[1])
          pEntries.append(t)
        return render_template(
            "art-entries.html",
            title="Art Entries",
            entries=entries,
            pEntries=pEntries,
            selectedtypes=selectedDataTypes,
            initial_view = 0
        )
    
    if "download" in request.form:
        iview = int(request.form["initial_view"])
        if iview != 1:
          selectedDataTypes = request.form.getlist("selectedTypes[]")
          entries = database.get_art_entry_by_type(selectedDataTypes)
          zip_name = "_".join(selectedDataTypes) + ".zip"
        else:
          entries = database.get_all("aiArt")
          zip_name = "all_art_entries.zip"

        file_names = []
        tmp_dir = ".temp_imgs" # hidden tmp folder for img zipping
        for entry in entries:
            file_names.append(entry[2])
        os.makedirs(tmp_dir, exist_ok=True)
        for fn in file_names:
            des_path = os.path.join(tmp_dir, os.path.basename(fn))
            shutil.copy(fn, des_path)
        with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
            for fn in file_names:
                zipf.write(os.path.join(tmp_dir, os.path.basename(fn)), os.path.basename(fn))
        files = send_file(zip_name, as_attachment=True)
        shutil.rmtree(tmp_dir)
        os.remove(zip_name)
        return files 
    
    # When user clicks on art id
    if "art_id" in request.form:
        sid = int(request.form["art_id"])  # art id
        iview = request.form["initial_view"]
        entries = database.get_art_by_id(sid)
        pEntries = [] # pEntries is the plant report entry id (the row id of Report)
        entryRow = database.get_art_entry_row_data(entries[0])
        for e in entryRow:
            pEntries.append(e[1])
        return render_template(
            "art-entries.html",
            title="View Art",
            view_art=sid,
            entries=entries,
            pEntries=pEntries,
            initial_view=iview,
            error=0,
        )

    entries = database.get_all("aiArt")
    pEntries = [] # pEntries is the plant report entry id (the row id of Report)
    for entry in entries:
        entryRow = database.get_art_entry_row_data(entry[0])
        t = []
        for e in entryRow:
          t.append(e[1])
        pEntries.append(t)

    return render_template(
        "art-entries.html",
        title="Art Entries",
        entries=entries,
        pEntries=pEntries,
        initial_view = 1
    )


################################################################################################


# Function to update database
def update_database(user_email):
    user = database.get_user(user_email)
    # Generates Authorization Token
    headers = {"Authorization": "Bearer " + user[4]}

    # Grab data from Farmbot Web App
    plants = farmbot_api.plants(headers)

    # Adds new unique plants to the database
    for plant in plants:
        database.add_unique_plant(plant, user[0])

    # drop any group tables to refresh
    database.clear_group_tables(app)

    group_plants = farmbot_api.get_plant_groups(user_email, database, headers)
    for k in group_plants:
        if not "plants" in k:
            continue  # a group doesnt have any plants in it
        database.add_plant_group(user_email, k["groupID"], k["groupName"])

    for k in group_plants:
        pid = set()
        if not "plants" in k:
            continue
        for p in k["plants"]:
            pid.add(database.get_id_from_ofslug(p))
        database.link_group_to_plants(k["groupID"], pid)

    return 0


# Function to get the weather data
def get_weather(location):
    # Checks if the weather is already in the database
    weather_id = database.check_weather(location)
    if weather_id == -1:
        # Grabs the current weather from WeatherStack
        weatherstack_data = weatherstack.current(location)
        # Adds the current weather to database
        weather_id = database.add_weather(weatherstack_data, location)

    return weather_id


# Function to capture plant data and save to database
def capture_plant(plantID, weatherID):
    # Take photo
    coor = database.get_plant_data(credentials[0], plantID)
    token = database.find_key(credentials[0])
    headers = {"Authorization": "Bearer " + token}
    now = datetime.datetime.now()

    raw_token = FarmbotToken.download_token(
        credentials[0], credentials[1], "https://my.farm.bot"
    )

    try:
        fb = Farmbot(raw_token)
        handler = Farmbot_handler(fb, coor[1], coor[2])
        event = threading.Event()
        thread = threading.Thread(target=fb.connect, name="foo", args=[handler])
        thread.start()
        while True:
            handler.try_next_job()
            if len(handler.queue) == 0:
                event.set()
                break
        thread.join(15)
        print("DISCONNECTING BROKER")
        handler.bot._connection.mqtt.disconnect()  # disconnect from broker
    except AttributeError as e:
        print(f"Error occured in capture_plant thread: {e}")

    # Grab image from Farmbot
    image_meta = farmbot_api.plant_images(headers, coor[1], coor[2])
    image_list = [image_meta[0]]
    temp_image_name_list = []

    #################### PlantCV ####################
    # Prepares each of the images
    for image in tqdm(image_list):
        temp_image_name_list.append(plantcv_interface.prepare_image(str(image)))
    # Grabs the data out of each of the images
    for image in tqdm(temp_image_name_list):
        image_name = str(image)
        plantCV_data = plantcv_interface.info_image(image_name, img_flag, image_meta[0])

    # Removes the original images
    # for image in tqdm(image_list):
    #     if os.path.exists(str(os.getcwd() + os.sep + "images" + os.sep + image)):
    #         os.remove(os.getcwd() + os.sep + "images" + os.sep + image)
    # # Deletes the modified images
    # for image in tqdm(temp_image_name_list):
    #     if os.path.exists(str(os.getcwd() + os.sep + "images" + os.sep + image)):
    #         os.remove(os.getcwd() + os.sep + "images" + os.sep + image)
    ################### End PlantCV ##################

    # Adds the data to the database
    database.plant_entry(plantID, plantCV_data, weatherID)
    entryID = database.get_entry_latest(plantID)
    output_folder = str(temp_image_name_list[0])[:-4]
    # Grab output images name
    folder_path = str(os.getcwd() + os.sep + "images" + os.sep + output_folder)
    obj_url = ""
    # Allocate time to write output images
    sleep(5)
    # Grab output images
    for file_name in os.listdir(folder_path):
        if file_name.endswith("_shapes.png"):
            obj_url = "/images/" + output_folder + "/" + file_name
            print(obj_url)

    green_url = "/images/" + output_folder + "/input_image.png"
    # Adds the images to the database
    database.photo_entry(entryID[0], image_meta[1], image_meta[2])
    database.photo_entry(entryID[0], green_url, image_meta[2])
    if obj_url != "":
        database.photo_entry(entryID[0], obj_url, image_meta[2])


# Capture plant data for scheduler
def capture_plant_job(scheduleID, plantID, user_email):
    # Take photo
    coor = database.get_plant_data(user_email, plantID)
    token = database.find_key(user_email)
    headers = {"Authorization": "Bearer " + token}

    user = database.get_user(user_email)
    location = user[3]
    weatherID = get_weather(location)

    try:
        # fb = Farmbot(raw_token)
        fb = Farmbot.login(email=credentials[0], password=credentials[1])
        handler = Farmbot_handler(fb, coor[1], coor[2])
        thread = threading.Thread(
            target=fb.connect, name="capture_data_job " + str(plantID), args=[handler]
        )
        thread.start()
        while True:
            handler_return = handler.try_next_job()
            if handler_return == False:
                print("!!!! event set is called")
                break
        thread.join(15)
        print("DISCONNECTING BROKER")
        handler.bot._connection.mqtt.disconnect()  # disconnect from broker
    except AttributeError as e:
        print(f"Error occured in capture_plant thread: {e}")

    # Grab image from Farmbot
    image_meta = farmbot_api.plant_images(headers, coor[1], coor[2])
    image_list = [image_meta[0]]
    temp_image_name_list = []

    #################### PlantCV ####################
    # Prepares each of the images
    for image in tqdm(image_list):
        temp_image_name_list.append(plantcv_interface.prepare_image(str(image)))
    # Grabs the data out of each of the images
    for image in tqdm(temp_image_name_list):
        image_name = str(image)
        plantCV_data = plantcv_interface.info_image(image_name, img_flag, image_meta[0])

    # Removes the original images
    # for image in tqdm(image_list):
    #     if os.path.exists(str(os.getcwd() + os.sep + "images" + os.sep + image)):
    #         os.remove(os.getcwd() + os.sep + "images" + os.sep + image)
    # # Deletes the modified images
    # for image in tqdm(temp_image_name_list):
    #     if os.path.exists(str(os.getcwd() + os.sep + "images" + os.sep + image)):
    #         os.remove(os.getcwd() + os.sep + "images" + os.sep + image)
    ################### End PlantCV ##################

    # Adds the data to the database
    database.plant_entry(plantID, plantCV_data, weatherID)
    entryID = database.get_entry_latest(plantID)
    output_folder = str(temp_image_name_list[0])[:-4]
    # Grab output images name
    folder_path = str(os.getcwd() + os.sep + "images" + os.sep + output_folder)
    obj_url = ""
    # Allocate time to write output images
    sleep(5)
    # Grab output images
    for file_name in os.listdir(folder_path):
        if file_name.endswith("_shapes.png"):
            obj_url = "/images/" + output_folder + "/" + file_name
            print(obj_url)

    green_url = "/images/" + output_folder + "/input_image.png"
    # Adds the images to the database
    database.photo_entry(entryID[0], image_meta[1], image_meta[2])
    database.photo_entry(entryID[0], green_url, image_meta[2])
    if obj_url != "":
        database.photo_entry(entryID[0], obj_url, image_meta[2])


if __name__ == "__main__":
    import os

    HOST = os.environ.get("SERVER_HOST", "localhost")

    print(f"Running on port {PORT}")
    print("Please login atleast once to start the schedules")

    # Start scheduler
    scheduler = BackgroundScheduler()
    scheduler.start()

    serve(app, port=PORT)
