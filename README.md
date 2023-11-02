# Farmbot Art

## How to run on Linux Local Server
1. Open the terminal and type the following commands, one after the other:  
`sudo apt-get update`  
`sudo apt upgrade`  
`sudo apt install python3 python3-pip –y`  
`pip install waitress flask Flask-APScheduler opencv-python-headless Pillow requests pytz numpy tqdm plantcv`

2. After those commands have completed, go to https://weatherstack.com/signup/free and sign up for a free API key.  
3. Have the Farmbot Art Application wherever you want to hold the files (desktop/documents etc.).  
4. Open the Config.json file, and place the Weatherstack API key next to the Weatherstack label.  
5. Next to the admin-accounts section, place any emails you may need as Admin. 
6. Open a terminal in the root directory of the project, and run “python3 app.py”.
7. The server should now be hosted on localhost:5003.

## How to run on Linux NGINX Server
1. Open the terminal and type the following commands, one after the other:  
`sudo apt-get update`  
`sudo apt upgrade`  
`sudo apt install python3 nginx python3-pip –y`  
`pip install waitress flask Flask-APScheduler opencv-python-headless Pillow requests pytz numpy tqdm plantcv`

2. After those commands have completed, go to https://weatherstack.com/signup/free and sign up for a free API key.  
3. Have the Farmbot Art Application wherever you want to hold the files (desktop/documents etc.).  
4. Open the Config.json file, and place the Weatherstack API key next to the Weatherstack label.  
5. Next to the admin-accounts section, place any emails you may need as Admin. 
6. Open a terminal, change the directory to /etc/nginx/sites-available/. Run the following command - `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx-selfsigned.key -out nginx-selfsigned.crt`.
7.  Open a command prompt window, navigating to the nginx folder, and type `nginx -s reload`.
8. Open another command prompt window, navigating to the project folder, and type "py app.py".

## How to run on Windows Local Server
1. Go to https://www.python.org/downloads/windows/. Click on download windows installer (64-bit) for Python 3.9.7. 
2. Run the downloaded installer, clicking on remove path limit if prompted.
3. Type the following lines into the command prompt:  
`py -m ensurepip –upgrade`  
`py -m pip install –upgrade pip`  
`py -m pip install waitress flask Flask-APScheduler opencv-python-headless Pillow requests pytz numpy tqdm plantcv`  

4. After those commands have completed, go to https://weatherstack.com/signup/free and sign up for a free API key.  
5. Have the Farmbot Art Application wherever you want to hold the files (desktop/documents etc.).  
6. Open the Config.json file, and place the Weatherstack API key next to the Weatherstack label.  
7. Next to the admin-accounts section, place any emails you may need as Admin.
8. Hit the windows button in the bottom right, and type “cmd”, clicking on the first option. 
9. Move the terminal into the correct directory.
10 Type the following line into the command prompt - `py app.py`.
11. The server should now be hosted on localhost:5003.

## How to run on Windows NGINX Server
1. Go to https://www.python.org/downloads/windows/. Click on download windows installer (64-bit) for Python 3.9.7. Run the installer.
2. Go to http://nginx.org/en/download.html, click on nginx/Windows-1.21.3. Unzip the folder.
3. Go to https://slproweb.com/download/Win64OpenSSL_Light-3_0_0.exe. Download the file "Win64 OpenSSL v3.0.0 Light". Run the executable, & unselect the donations.
4. Go to nginx-1.21.3/conf and replace the nginx.conf file with the one in ps2101/nginx/windows/nginx.conf.
5. Hit the windows button, and type openssl clicking on the first option, opening a special terminal.
6. hange directories to be in the nginx-1.21.3/conf, and run the following `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx-selfsigned.key -out nginx-selfsigned.crt`.
7. Double click on NGINX.exe
8. Type the following lines into the command prompt:  
`py -m ensurepip --upgrade`  
`py -m pip install --upgrade pip`  
`py -m pip install waitress flask Flask-APScheduler opencv-python-headless Pillow requests pytz numpy tqdm plantcv`  
9. After those commands have completed, go to https://weatherstack.com/signup/free and sign up for a free API key.  
10. Have the Farmbot Art Application wherever you want to hold the files (desktop/documents etc.).  
11. Open the Config.json file, and place the Weatherstack API key next to the Weatherstack label.  
12. Next to the admin-accounts section, place any emails you may need as Admin. 
13.  Open a command prompt window, navigating to the nginx folder, and type `nginx -s reload`.
14. Open another command prompt window, navigating to the project folder, and type "py app.py".