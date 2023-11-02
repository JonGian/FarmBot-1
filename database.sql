PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
        emailAddress VarChar(50) PRIMARY KEY NOT NULL UNIQUE,
        name VarChar(50),
        userType VarChar(50),
        location VarChar(80),
        token TEXT NOT NULL,
        token_timeout TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS farmbot (
        farmbotID int(25) PRIMARY KEY,
        farmbotName VarChar(50),
        userEmail VarChar(50),
        FOREIGN KEY(userEmail) REFERENCES users(emailAddress)
);

CREATE TABLE IF NOT EXISTS plants (
        plantID int(25) PRIMARY KEY,
        farmbotID int(25),
        species VarChar(50),
        plantedDate date,
        X int(25),
        Y int(25),
        openfarmSlug VarChar(50),
        -- Used for grouping plants for the scheduler
        FOREIGN KEY(farmbotID) REFERENCES farmbot(farmbotID)
);

CREATE TABLE IF NOT EXISTS picturesOfPlants (
        plantPhotoID INTEGER PRIMARY KEY AUTOINCREMENT,
        entryID INTEGER,
        photoURL VarChar(255),
        dateAndTime datetime,
        FOREIGN KEY(entryID) REFERENCES plantEntries(entryID)
);

CREATE TABLE IF NOT EXISTS plantEntries (
        entryID INTEGER PRIMARY KEY AUTOINCREMENT,
        plantID int(25),
        dateAndTime datetime,
        R float(25),
        G float(25),
        B float(25),
        leafArea float(25),
        weatherID INTEGER,
        leafCount INTEGER,
        leafCircularity float(25),
        leafSolidity float(25),
        leafAspectRatio float(25),
        FOREIGN KEY(plantID) REFERENCES plants(plantID),
        FOREIGN KEY(weatherID) REFERENCES weather(weatherID)
);

CREATE TABLE IF NOT EXISTS weather (
        weatherID INTEGER PRIMARY KEY AUTOINCREMENT,
        dateAndTime datetime,
        location VarChar(80),
        weatherCondition VarChar(80),
        temperature int(25),
        humidity int(25),
        windSpeed int(25),
        precip int(25),
        cloudCover int(25)
);

CREATE TABLE IF NOT EXISTS schedules (
        scheduleID INTEGER PRIMARY KEY AUTOINCREMENT,
        schedulePlantID INTEGER,
        scheduleStartDate datetime,
        scheduleRepeats VarChar(80),
        scheduleDescription VarChar(100),
        scheduleEmail VarChar(50),
        FOREIGN KEY(scheduleEmail) REFERENCES users(emailAddress) FOREIGN KEY(schedulePlantID) REFERENCES plants(plantID)
);

-- plant group linking table
CREATE TABLE IF NOT EXISTS plant_group_to_plant (
        plantID int(25),
        groupID INTEGER,
        PRIMARY KEY (plantID, groupID),
        FOREIGN KEY (plantID) REFERENCES plants(plantID),
        FOREIGN KEY (groupID) REFERENCES plantGroups(groupID)
);

CREATE TABLE IF NOT EXISTS plantGroups (
        groupID INTEGER PRIMARY KEY,
        groupName TEXT,
        userEmail VarChar(50),
        FOREIGN KEY(userEmail) REFERENCES users(emailAddress)
);

CREATE TABLE IF NOT EXISTS aiArt (
        artID INTEGER PRIMARY KEY AUTOINCREMENT,
        artPrompt TEXT,
        artPosPrompt TEXT,
        artNegPrompt TEXT,
        artFilePath TEXT,
        artDate datetime,
        artDataTypes TEXT
);

CREATE TABLE IF NOT EXISTS aiart_to_entry (
        artID INTEGER,
        entryID INTEGER,
        PRIMARY KEY (artID, entryID),
        FOREIGN KEY (artID) REFERENCES aiArt(artID),
        FOREIGN KEY (entryID) REFERENCES plantEntries(entryID)
);