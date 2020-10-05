# FRI timetable to Google calendar
This year, because of COVID19, the faculty doesn't provide personalized timetables as usually, so I made this simple project that scrapes the official timetable data and then allows you to select the desired lectures and import them to your Google calendar. I also wanted to try out Scrapy and Curses.

# How to use
### Clone the repo
    git clone https://github.com/nikp00/fri_timetable_to_google_calendar.git
## 1.1  Windows
You first need to install all the Python packages.

    pip install -r requirements.txt

Then you need to install Curses (it's not included in the requirements.txt, because this step is only necessary on Windows)

    pip install windows-curses
## 1.2 Linux
You just need to install all the Python packages.

    pip3 install -r requirements.txt

You must also provide the Google Auth data.
1.  Go to https://developers.google.com/calendar/quickstart/python
2. Click on _**Enable the Google Calendar API**_ 
3. Enter a project name of your choice and click _**Next**_
4. Select _**Desktop app**_ and click _**Create**_
5. Then click _**DOWNLOAD CLIENT CONFIGURATION**_
6. Save the .json file to the _**fri_timetable_to_google_calendar**_

## 2. Run the "GUI" (TUI - text-based user interfaces)
``python main <URL TO TIMETABLE>``  or  ``python3 main.py <URL TO TIMETABLE``
1. First you select the subjects that you want to add to your calendar.
![First screen](/img/gui_2.png)
2. Then you select the lectures/lab work that you want to add. All lectures are selected by default. When you select lab work that has multiple time period options, the non selected ones are grayed out.
![First screen](/img/gui_4.png)
3. Add to calendar.
![First screen](/img/calendar_web.png)
![First screen](/img/calendar_mobile.png)

## 3. Delete inserted events
When you add lectures to your calendar, their IDs are saved in a .csv file (_**events_ids.csv**_) so you can delete the automaticly.
``python delete_events.py``  or  ``python3 delete_events.py``
