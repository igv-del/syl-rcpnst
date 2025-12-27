import configparser

# Load config the same way app.py does
config = configparser.ConfigParser()
config.read('config.ini')

# Get the calendar URL
calendar_url = config.get('calendar', 'calendar_url', fallback='NO URL FOUND')

with open('calendar_test_output.txt', 'w') as f:
    f.write("=" * 80 + "\n")
    f.write("CALENDAR URL TEST\n")
    f.write("=" * 80 + "\n\n")
    f.write(f"Calendar URL from config.ini:\n{calendar_url}\n\n")
    f.write(f"URL Length: {len(calendar_url)} characters\n\n")
    
    expected = "https://calendar.google.com/calendar/appointments/schedules/AcZssZ0pc_HNDTuFq4i9jaFyYtPKGCERR07B-IkELiPkwtKAhdae1VdvK-6BIGY38qdSbXjZLfuJyQHh?gv=true"
    f.write(f"Expected URL:\n{expected}\n\n")
    f.write(f"Expected Length: {len(expected)} characters\n\n")
    f.write(f"URLs match: {calendar_url == expected}\n")
    f.write("=" * 80 + "\n")

print("Test complete! Check calendar_test_output.txt for results")
