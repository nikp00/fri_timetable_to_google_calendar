import curses
import datetime
import os.path
import pickle
import re
import sys
from collections import defaultdict

import scrapy
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


from itemloaders.processors import TakeFirst, MapCompose
from scrapy import signals
from scrapy.crawler import Crawler, CrawlerProcess
from scrapy.loader import ItemLoader

# Define global variables
COLORS = {}
PAD_DISPLAY_HEIGHT = 0
PAD_WIDTH = 0

DAYS = {
    "ponedeljek": 0,
    "torek": 1,
    "sreda": 2,
    "četrtek": 3,
    "petek": 4
}

DAYS_EN = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

SCOPES = ['https://www.googleapis.com/auth/calendar']

ITEMS = []

URL = []


class Subject:
    def __init__(self, classroom, day, prof, subject, time):
        self.classroom = classroom
        self.day = day
        self.prof = prof
        self.subject = subject
        self.start_time = int(time[0])
        self.end_time = int(time[1])
        self.is_selected = False
        self.index = None

    def __str__(self):
        return f"{self.subject}, {self.classroom}, {self.prof}, {self.start_time}:00 - {self.end_time}:00"

    def __repr__(self):
        return f"{self.subject}, {self.classroom}, {self.prof}, {self.start_time} - {self.end_time}"


def init_subjects():
    """
    Creates Subject objects from the scraped data
    """
    subjects = []
    for e in ITEMS:
        subjects.append(Subject(e["classroom"], e["day"], e["prof"], e["subject"], e["time"]))

    return subjects


def update_pad_position(key, pad_pos, current_selected_row, pad_rows):
    PAD_DISPLAY_HEIGHT
    """
    Updates pad position, requires the key pressed (UP, DOWN), the current pad position, current selected (highlighted)
     row, the # of rows and columns in the pad. Returns the new pad position and the new currently selected row.
    """
    if key == curses.KEY_DOWN:
        if pad_pos < pad_rows - PAD_DISPLAY_HEIGHT - 1:
            pad_pos += 1
        if current_selected_row < pad_rows - 1:
            current_selected_row += 1
    if key == curses.KEY_UP:
        if pad_pos > 0:
            pad_pos -= 1
        if current_selected_row > 0:
            current_selected_row -= 1

    return pad_pos, current_selected_row


def render_nav_subject_selection(stdscr):
    """
    Render the "nav" elements in the subject selection section
    """

    stdscr.attron(curses.color_pair(COLORS["nav"]))
    stdscr.addstr(PAD_DISPLAY_HEIGHT + 1, 0,
                  "{:^{places}}".format("SPACE: select     ⇅: up/dow      ENTER: advance       ESC: exit",
                                        places=stdscr.getmaxyx()[1] - 1))
    stdscr.addstr(0, PAD_WIDTH, "{:^{places}}".format("SELECTED SUBJECTS", places=PAD_WIDTH * 2))
    stdscr.attroff(curses.color_pair(COLORS["nav"]))


def render_subject_selection_section(pad, unique_subjects, current_selected_row, pad_pos):
    """
    Render the subject in the selection section
    """
    for i, e in enumerate(unique_subjects):
        out = ""
        if e.is_selected:
            out = "(x) {: <{places}}|".format(e.subject, places=PAD_WIDTH - 6)
        else:
            out = "( ) {: <{places}}|".format(e.subject, places=PAD_WIDTH - 6)

        if i == current_selected_row:
            pad.attron(curses.color_pair(1))
            pad.addstr(i, 0, out)
            pad.attroff(curses.color_pair(1))
        else:
            pad.addstr(i, 0, out)
    pad.refresh(pad_pos, 0, 0, 0, PAD_DISPLAY_HEIGHT, PAD_WIDTH)


def select_subjects(stdscr, subjects):
    """
    Gets all the subjects and displays them so the user can select only the subject he is interested in.
    """

    global PAD_DISPLAY_HEIGHT
    global PAD_WIDTH

    stdscr.refresh()

    # Filter out unique subject names
    unique_subjects = []
    for e in subjects:
        if all(e.subject != f.subject for f in unique_subjects):
            unique_subjects.append(e)

    pad_rows = len(unique_subjects)

    # Subtract 1 from the displayable height (# rows) because of the bottom commands bar
    PAD_DISPLAY_HEIGHT = stdscr.getmaxyx()[0] - 1 - 1
    # Add 10 to the pad width (# columns) for additional padding
    PAD_WIDTH = max(len(e.subject) for e in unique_subjects) + 10

    # Init the main pad (left)
    pad = curses.newpad(pad_rows, PAD_WIDTH)
    # Init the pad that displays the selected subjects (right)
    pad_selected = curses.newpad(pad_rows, PAD_WIDTH * 2)

    pad_pos = 0
    current_selected_row = 0

    # Sort subject for better readability
    unique_subjects = sorted(unique_subjects, key=lambda x: x.subject.upper())

    # Render "nav" elements
    render_nav_subject_selection(stdscr)

    # Render the subjects before entering the loop. getch() is a blocking function so the subjects
    # wouldnt be displayed if the the render function wasn't called before
    render_subject_selection_section(pad, unique_subjects, current_selected_row, pad_pos)

    while True:
        key = stdscr.getch()
        pad_pos, current_selected_row = update_pad_position(key, pad_pos, current_selected_row, pad_rows)

        # Check key presses. If the ESC key is pressed the program will close,
        # else if the ENTER key is pressed the function will return the selected subjects
        if key == 27:
            return False, unique_subjects
        if key == 32:
            unique_subjects[current_selected_row].is_selected ^= True
        if key == curses.KEY_ENTER or key in (10, 13) and len(
                list(filter(lambda x: x.is_selected, unique_subjects))) > 0:
            return True, [e for e in unique_subjects if e.is_selected]

        render_subject_selection_section(pad, unique_subjects, current_selected_row, pad_pos)

        # Render the already selected subjects in the right side pad
        pad_selected.clear()
        row = 0
        for i, e in enumerate(filter(lambda x: x.is_selected, unique_subjects)):
            pad_selected.addstr(row, i % 2 * PAD_WIDTH, e.subject)
            row += i % 2
        pad_selected.refresh(0, 0, 1, PAD_WIDTH, PAD_DISPLAY_HEIGHT - 1, PAD_WIDTH * 3)


def render_lecture_selection_section(pad, subjects_sorted_by_days, current_selected_row, pad_pos, already_selected):
    idx = 0
    for i in range(5):
        if i in subjects_sorted_by_days.keys():
            pad.attron(curses.color_pair(COLORS["days"]))
            pad.addstr(idx, 0, "{:^{places}}".format(DAYS_EN[i], places=PAD_WIDTH))
            pad.attroff(curses.color_pair(COLORS["days"]))
            idx += 1
            for sub in subjects_sorted_by_days[i]:
                out = ""
                if sub.is_selected:
                    out = f"(x) {str(sub)}"
                else:
                    out = f"( ) {str(sub)}"
                if current_selected_row == idx:
                    pad.attron(curses.color_pair(COLORS["current"]))
                    pad.addstr(idx, 0, out)
                    pad.attroff(curses.color_pair(COLORS["current"]))
                elif sub.subject in already_selected and not sub.is_selected:
                    pad.attron(curses.color_pair(COLORS["already_selected"]))
                    pad.addstr(idx, 0, out)
                    pad.attroff(curses.color_pair(COLORS["already_selected"]))
                elif sub.is_selected:
                    pad.attron(curses.color_pair(COLORS["selected"]))
                    pad.addstr(idx, 0, out)
                    pad.attroff(curses.color_pair(COLORS["selected"]))
                else:
                    pad.addstr(idx, 0, out)
                sub.index = idx
                idx += 1

    pad.refresh(pad_pos, 0, 0, 0, PAD_DISPLAY_HEIGHT, PAD_WIDTH)


def render_nav_lecture_selection(stdscr):
    """
    Render the "nav" elements in the subject time section
    """

    stdscr.attron(curses.color_pair(COLORS["nav"]))
    stdscr.addstr(PAD_DISPLAY_HEIGHT + 1, 0,
                  "{:^{places}}".format("SPACE: select     ⇅: up/dow      ENTER: advance       ESC: exit",
                                        places=stdscr.getmaxyx()[1] - 1))
    stdscr.attroff(curses.color_pair(COLORS["nav"]))


def select_lectures(stdscr, selected_subjects, subjects):
    global PAD_WIDTH

    # Get all lectures of the same subject
    selected_subjects_names = {e.subject for e in selected_subjects}
    selected_subjects = set()
    for e in subjects:
        if e.subject in selected_subjects_names:
            selected_subjects.add(e)

    selected_subjects = list(selected_subjects)

    # Create a default dict that organizes subjects by day
    subjects_sorted_by_days = defaultdict(list)
    for e in selected_subjects:
        if re.search(r"(LV$)|(AV$)", e.subject) is None:
            e.is_selected = True
        else:
            e.is_selected = False
        subjects_sorted_by_days[DAYS[e.day]].append(e)

    # Sort the lectures by the start time
    for k, v in subjects_sorted_by_days.items():
        subjects_sorted_by_days[k] = sorted(v, key=lambda x: x.start_time)

    pad_rows = len(selected_subjects) + len(subjects_sorted_by_days)

    # Add 10 to the pad width (# columns) for additional padding
    PAD_WIDTH = max(len(str(e)) for e in selected_subjects) + 5

    # Init the main pad (left)
    pad = curses.newpad(pad_rows, PAD_WIDTH)

    pad_pos = 0
    current_selected_row = 1

    # Render "nav" elements
    render_nav_lecture_selection(stdscr)

    # Render the subjects before entering the loop. getch() is a blocking function so the subjects
    # wouldn't be displayed if the the render function wasn't called before
    render_lecture_selection_section(pad, subjects_sorted_by_days, current_selected_row, pad_pos, {})

    while True:
        key = stdscr.getch()
        pad_pos, current_selected_row = update_pad_position(key, pad_pos, current_selected_row, pad_rows)

        # Check key presses. If the ESC key is pressed the program will close,
        # else if the ENTER key is pressed the function will return the selected subjects
        if key == 27:
            return False, {}
        if key == 32:
            # Terrible solution (:
            for e in subjects_sorted_by_days.values():
                for sub in e:
                    if sub.index == current_selected_row:
                        sub.is_selected ^= True
                        break

        if key == curses.KEY_ENTER or key in (10, 13):
            selected_lectures = []
            for day in subjects_sorted_by_days.values():
                for lecture in day:
                    if lecture.is_selected:
                        selected_lectures.append(lecture)
            return True, selected_lectures

        already_selected = set()
        for e in subjects_sorted_by_days.values():
            for sub in e:
                if sub.is_selected:
                    already_selected.add(sub.subject)

        render_lecture_selection_section(pad, subjects_sorted_by_days, current_selected_row, pad_pos, already_selected)


def build_service():
    """
    Builds the google API service (code from google docs)
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds, cache_discovery=False)

    return service


def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)


def add_event(service, lecture, color_dict):
    day = next_weekday(datetime.datetime.now(), DAYS[lecture.day])
    day = day.replace(minute=0, microsecond=0)
    color = color_dict.get(lecture.subject[:lecture.subject.index("_")], "undefined")
    event = {
        'summary': f'{lecture.subject}   |   {lecture.classroom}   |   {lecture.prof}',
        'location': 'FRI, Večna pot 113, Ljubljana',
        # 'description': f'{lecture.classroom}, {lecture.prof}',
        'start': {
            'dateTime': f'{day.replace(hour=lecture.start_time).astimezone().isoformat()}',
            'timeZone': 'Europe/Ljubljana',
        },
        'end': {
            'dateTime': f'{day.replace(hour=lecture.end_time).astimezone().isoformat()}',
            'timeZone': 'Europe/Ljubljana',
        },
        'recurrence': [
            'RRULE:FREQ=WEEKLY;'
        ],
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 30},
            ],
        },
        "colorId": color
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    return event.get('id')


def add_to_calendar(lectures):
    service = build_service()
    event_ids = []
    color_dict = dict()
    i = 1
    for e in lectures:
        e = e.subject
        e = e[:e.index("_")]
        if e not in color_dict.keys():
            color_dict[e] = i
            i += 1
        if i > 11:
            break
    for lecture in lectures:
        event_ids.append(add_event(service, lecture, color_dict))

    with open("events_ids.csv", "a") as file:
        for e in event_ids:
            file.write(f"{e},")
        file.close()


def gui(stdscr):
    # Reads the scv file
    subjects = init_subjects()

    # Init the color pairs
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_RED)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_GREEN)

    # Add zhe color pairs indexes to the dictionary
    global COLORS
    COLORS = {
        "current": 1,
        "nav": 2,
        "days": 3,
        "already_selected": 4,
        "selected": 5
    }
    curses.curs_set(0)

    continue_, selected_subjects = select_subjects(stdscr, subjects)

    if continue_:
        stdscr.clear()
        stdscr.refresh()
        continue_, selected_lectures = select_lectures(stdscr, selected_subjects, subjects)

    if continue_:
        add_to_calendar(selected_lectures)


"""

    Scrapy

"""


class TimetableSpider(scrapy.Spider):
    name = "timetable"

    def __init__(self, *args, **kwargs):
        super(TimetableSpider, self).__init__(*args, **kwargs)
        self.start_urls = URL

    def start_requests(self):
        yield scrapy.Request(self.start_urls[0], callback=self.parse)

    def parse(self, response):
        days = response.css(".grid-day-column")
        for day in days:
            subjects = day.css(".grid-entry")
            for subject in subjects:
                text = subject.css(".entry-hover").get()
                elements = []
                for e in text.split("\n"):
                    e = e.strip()
                    e = e.replace("<br>", ",")
                    elements.append(e)
                time = elements[1].split(" ")
                elements = elements[1: 3] + elements[4:]

                elements[2] = subject.css(".link-subject::text").get()

                subject_item = ItemLoader(item=SubjectItem(), selector=subject)
                subject_item.add_value("day", time[0])
                subject_item.add_value("time", (time[1][:time[1].index(":")], time[3][:time[3].index(":")]))
                subject_item.add_value("classroom", elements[1])
                subject_item.add_value("subject", elements[2])
                subject_item.add_value("prof", elements[3])

                yield subject_item.load_item()


def remove_comma(value):
    return " ".join(value).replace(",", "")


def edit_profs(value):
    elements = value.split(",")
    value = ""
    for i, e in enumerate(elements):
        if i % 2 == 0:
            value += e
        else:
            value += e + ", "
    return re.sub(r",*\s$", "", value)


class SubjectItem(scrapy.Item):
    day = scrapy.Field(
        output_processor=TakeFirst()
    )
    time = scrapy.Field(
        input_processor=lambda x: map(lambda y: int(y), x)
    )
    classroom = scrapy.Field(
        output_processor=TakeFirst()
    )
    subject = scrapy.Field(
        output_processor=TakeFirst()
    )
    prof = scrapy.Field(
        input_processor=MapCompose(edit_profs),
        output_processor=TakeFirst()
    )


def collect_items(item, response, spider):
    ITEMS.append(item)


if __name__ == "__main__":

    if len(sys.argv) > 1 and re.search(r"^https:\/\/urnik\.fri\.uni-lj\.si\/timetable\/.*", sys.argv[1]) is not None:
        URL.append(sys.argv[1])

        crawler = Crawler(TimetableSpider)
        crawler.signals.connect(collect_items, signals.item_scraped)

        process = CrawlerProcess()
        process.crawl(crawler)
        process.start()

        curses.wrapper(gui)
    else:
        print("Invalid URL")
