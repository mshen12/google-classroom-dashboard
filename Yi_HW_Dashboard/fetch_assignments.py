"""
Google Classroom Homework Dashboard
Fetches all assignments from Google Classroom and opens a visual HTML page
grouped by subject with due dates and submission status.
"""

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
import json
import webbrowser
import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes needed to read courses and assignments
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
OUTPUT_FILE = "assignments.html"

# Colors cycled through for each course card header
COURSE_COLORS = [
    "#4f46e5",  # indigo
    "#0891b2",  # cyan
    "#059669",  # emerald
    "#d97706",  # amber
    "#dc2626",  # red
    "#7c3aed",  # violet
    "#db2777",  # pink
    "#65a30d",  # lime
]


def authenticate():
    """Handle Google OAuth 2.0 authentication."""
    creds = None

    if not Path(CREDENTIALS_FILE).exists():
        print(f"ERROR: '{CREDENTIALS_FILE}' not found in this folder.")
        print("Please follow the instructions in SETUP.md to get your credentials.")
        raise SystemExit(1)

    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            creds.refresh(Request())
        else:
            print("Opening browser for Google sign-in (first time only)...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        print("Authentication successful. Token saved.")

    return creds


def parse_due_date(coursework):
    """Parse dueDate and dueTime from coursework dict, return datetime or None."""
    due = coursework.get("dueDate")
    if not due:
        return None
    year = due.get("year", 1970)
    month = due.get("month", 1)
    day = due.get("day", 1)
    due_time = coursework.get("dueTime")
    if due_time is None:
        hour, minute = 23, 59  # no time set — default to end of day
    else:
        hour = due_time.get("hours", 23)
        minute = due_time.get("minutes", 0)  # missing minutes means :00
    dt_utc = datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc)
    return dt_utc.astimezone().replace(tzinfo=None)  # convert to local time, strip tz for consistency


def format_due_date(dt):
    """Return a human-friendly due date string."""
    if dt is None:
        return "No due date"
    today = datetime.date.today()
    due_date = dt.date()
    diff = (due_date - today).days
    day_str = f"{dt.strftime('%b')} {dt.day}, {dt.year}"  # e.g. "Mar 12, 2026"
    time_str = dt.strftime("%I:%M %p").lstrip("0")  # e.g. "11:59 PM"

    if dt < datetime.datetime.now():
        return f"{day_str} at {time_str} (Overdue)"
    elif diff == 0:
        return f"Today at {time_str}"
    elif diff == 1:
        return f"Tomorrow at {time_str}"
    elif diff <= 7:
        weekday = dt.strftime("%A")  # e.g. "Wednesday"
        return f"{weekday} at {time_str}"
    else:
        return f"{day_str} at {time_str}"


def due_date_css_class(dt):
    """Return a CSS class based on urgency of due date."""
    if dt is None:
        return "due-none"
    today = datetime.date.today()
    diff = (dt.date() - today).days
    if dt < datetime.datetime.now():
        return "due-overdue"
    elif diff < 3:
        return "due-soon"
    else:
        return "due-ok"


def get_submission_state(submission):
    """Map submission state to a display label and CSS class."""
    if submission is None:
        return "Unknown", "state-unknown"
    state = submission.get("state", "")
    late = submission.get("late", False)
    if state == "TURNED_IN":
        return "Turned In", "state-turned-in"
    elif state == "RETURNED":
        grade = submission.get("assignedGrade")
        if grade is not None:
            return f"Graded ({grade})", "state-graded"
        return "Returned", "state-returned"
    elif late:
        return "Late", "state-late"
    elif state == "NEW":
        return "Not Started", "state-assigned"
    else:
        return "Assigned", "state-assigned"


def fetch_data(service):
    """Fetch all active courses and their assignments with submission status."""
    print("Fetching active courses...")
    courses_result = service.courses().list(
        studentId="me", courseStates=["ACTIVE"]
    ).execute()
    courses = courses_result.get("courses", [])

    if not courses:
        print("No active courses found.")
        return []

    print(f"Found {len(courses)} course(s).")
    all_courses = []

    for course in courses:
        course_id = course["id"]
        course_name = course.get("name", "Unknown Course")
        section = course.get("section", "")
        print(f"  Fetching assignments for: {course_name}...")

        try:
            cw_result = service.courses().courseWork().list(
                courseId=course_id,
                orderBy="dueDate asc",
                courseWorkStates=["PUBLISHED"],
            ).execute()
            coursework_list = cw_result.get("courseWork", [])
        except HttpError as e:
            print(f"    Warning: Could not fetch coursework for {course_name}: {e}")
            coursework_list = []

        assignments = []
        for cw in coursework_list:
            cw_id = cw["id"]
            # Fetch the student's own submission for this assignment
            try:
                sub_result = service.courses().courseWork().studentSubmissions().list(
                    courseId=course_id,
                    courseWorkId=cw_id,
                    userId="me",
                ).execute()
                submissions = sub_result.get("studentSubmissions", [])
                submission = submissions[0] if submissions else None
            except HttpError:
                submission = None

            due_dt = parse_due_date(cw)
            status_label, status_class = get_submission_state(submission)
            max_points = cw.get("maxPoints")

            assignments.append({
                "title": cw.get("title", "Untitled"),
                "description": cw.get("description", ""),
                "due_dt": due_dt,
                "due_label": format_due_date(due_dt),
                "due_class": due_date_css_class(due_dt),
                "status_label": status_label,
                "status_class": status_class,
                "max_points": max_points,
                "link": cw.get("alternateLink", "#"),
            })

        # Sort: no due date goes last, rest sorted by due date ascending
        assignments.sort(key=lambda a: (a["due_dt"] is None, a["due_dt"] or datetime.datetime.max))

        all_courses.append({
            "name": course_name,
            "section": section,
            "assignments": assignments,
        })

    return all_courses


def escape_html(text):
    """Escape special HTML characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_html(courses):
    """Generate a self-contained HTML page from the courses data."""
    now = datetime.datetime.now()
    now_str = f"{now.strftime('%B')} {now.day}, {now.year} at {now.strftime('%I:%M %p').lstrip('0')}"
    total_assignments = sum(len(c["assignments"]) for c in courses)

    # Build course cards HTML
    cards_html = ""
    for i, course in enumerate(courses):
        color = COURSE_COLORS[i % len(COURSE_COLORS)]
        assignments = course["assignments"]
        section_html = f'<span class="section">{escape_html(course["section"])}</span>' if course["section"] else ""

        if not assignments:
            rows_html = '<div class="no-assignments">No assignments posted</div>'
        else:
            rows_html = ""
            for a in assignments:
                # Skip overdue assignments older than 3 months
                if a['due_dt'] is not None and a['due_class'] == 'due-overdue':
                    days_overdue = (datetime.date.today() - a['due_dt'].date()).days
                    if days_overdue > 90:
                        continue

                points_html = f'<span class="points">{a["max_points"]} pts</span>' if a["max_points"] is not None else ""
                desc = a["description"][:120] + "..." if len(a["description"]) > 120 else a["description"]
                desc_html = f'<div class="desc">{escape_html(desc)}</div>' if desc else ""

                # Determine filter category
                if a['status_class'] in ('state-turned-in', 'state-graded', 'state-returned'):
                    filter_tag = "turned-in"
                elif a['due_class'] == 'due-overdue':
                    filter_tag = "overdue"
                elif a['due_class'] == 'due-soon':
                    filter_tag = "due-soon"
                else:
                    filter_tag = "upcoming"

                rows_html += f"""
                <a class="assignment" data-filter="{filter_tag}" href="{escape_html(a['link'])}" target="_blank">
                  <div class="assignment-left">
                    <div class="title">{escape_html(a['title'])}</div>
                    {desc_html}
                  </div>
                  <div class="assignment-right">
                    {points_html}
                    <span class="due-chip {a['due_class']}">{escape_html(a['due_label'])}</span>
                    <span class="status-badge {a['status_class']}">{escape_html(a['status_label'])}</span>
                  </div>
                </a>"""

        cards_html += f"""
        <div class="card">
          <div class="card-header" style="background:{color}">
            <div class="course-name">{escape_html(course['name'])}</div>
            {section_html}
            <div class="assignment-count">{len(assignments)} assignment{'s' if len(assignments) != 1 else ''}</div>
          </div>
          <div class="card-body">
            {rows_html}
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Homework Dashboard</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f0f2f5;
      color: #1a1a2e;
      min-height: 100vh;
    }}

    header {{
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      color: white;
      padding: 28px 32px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.2);
    }}

    header h1 {{
      font-size: 1.8rem;
      font-weight: 700;
      letter-spacing: -0.5px;
    }}

    .home-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 14px;
      padding: 5px 14px;
      border-radius: 20px;
      background: rgba(255,255,255,0.15);
      color: white;
      text-decoration: none;
      font-size: 0.82rem;
      font-weight: 600;
      transition: background 0.15s;
    }}

    .home-btn:hover {{
      background: rgba(255,255,255,0.28);
    }}

    .meta {{
      margin-top: 6px;
      font-size: 0.85rem;
      opacity: 0.7;
    }}

    .filter-bar {{
      display: flex;
      gap: 10px;
      padding: 14px 32px;
      background: white;
      border-bottom: 1px solid #e5e7eb;
      flex-wrap: wrap;
    }}

    .filter-btn {{
      display: flex;
      align-items: center;
      gap: 7px;
      padding: 7px 16px;
      border-radius: 20px;
      border: 2px solid transparent;
      background: #f3f4f6;
      color: #374151;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }}

    .filter-btn:hover {{
      filter: brightness(0.95);
    }}

    .filter-btn.active {{
      border-color: currentColor;
    }}

    .filter-btn .dot {{
      width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0;
    }}

    .filter-btn[data-filter="all"].active      {{ background: #1a1a2e; color: white; }}
    .filter-btn[data-filter="overdue"].active  {{ background: #fee2e2; color: #991b1b; border-color: #fca5a5; }}
    .filter-btn[data-filter="due-soon"].active {{ background: #fef3c7; color: #92400e; border-color: #fcd34d; }}
    .filter-btn[data-filter="upcoming"].active {{ background: #dcfce7; color: #166534; border-color: #86efac; }}
    .filter-btn[data-filter="turned-in"].active{{ background: #dbeafe; color: #1d4ed8; border-color: #93c5fd; }}

    .card.hidden {{ display: none; }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
      gap: 20px;
      padding: 24px 32px;
      max-width: 1400px;
      margin: 0 auto;
    }}

    .card {{
      background: white;
      border-radius: 12px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.08);
      overflow: hidden;
      transition: box-shadow 0.2s;
    }}

    .card:hover {{
      box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    }}

    .card-header {{
      padding: 16px 20px;
      color: white;
    }}

    .course-name {{
      font-size: 1.05rem;
      font-weight: 700;
      line-height: 1.3;
    }}

    .section {{
      font-size: 0.8rem;
      opacity: 0.85;
      margin-top: 2px;
      display: block;
    }}

    .assignment-count {{
      margin-top: 6px;
      font-size: 0.78rem;
      opacity: 0.8;
      background: rgba(255,255,255,0.2);
      display: inline-block;
      padding: 2px 8px;
      border-radius: 20px;
    }}

    .card-body {{
      padding: 8px 0;
    }}

    .assignment {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      padding: 12px 20px;
      border-bottom: 1px solid #f3f4f6;
      text-decoration: none;
      color: inherit;
      transition: background 0.15s;
    }}

    .assignment:last-child {{
      border-bottom: none;
    }}

    .assignment:hover {{
      background: #f9fafb;
    }}

    .assignment-left {{
      flex: 1;
      min-width: 0;
    }}

    .title {{
      font-size: 0.92rem;
      font-weight: 600;
      color: #111827;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .desc {{
      font-size: 0.78rem;
      color: #9ca3af;
      margin-top: 3px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .assignment-right {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 5px;
      flex-shrink: 0;
    }}

    .points {{
      font-size: 0.75rem;
      color: #6b7280;
      font-weight: 500;
    }}

    .due-chip {{
      font-size: 0.73rem;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 20px;
      white-space: nowrap;
    }}

    .due-overdue {{ background: #fee2e2; color: #991b1b; }}
    .due-soon    {{ background: #fef3c7; color: #92400e; }}
    .due-ok      {{ background: #dcfce7; color: #166534; }}
    .due-none    {{ background: #f3f4f6; color: #6b7280; }}

    .status-badge {{
      font-size: 0.7rem;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 20px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      white-space: nowrap;
    }}

    .state-turned-in  {{ background: #dbeafe; color: #1d4ed8; }}
    .state-graded     {{ background: #d1fae5; color: #065f46; }}
    .state-returned   {{ background: #e0e7ff; color: #3730a3; }}
    .state-late       {{ background: #fee2e2; color: #991b1b; }}
    .state-assigned   {{ background: #f3f4f6; color: #374151; }}
    .state-unknown    {{ background: #f3f4f6; color: #9ca3af; }}

    .no-assignments {{
      padding: 20px;
      text-align: center;
      color: #9ca3af;
      font-size: 0.875rem;
      font-style: italic;
    }}

    footer {{
      text-align: center;
      padding: 24px;
      color: #9ca3af;
      font-size: 0.8rem;
    }}

    @media (max-width: 600px) {{
      .grid {{ grid-template-columns: 1fr; padding: 16px; }}
      header {{ padding: 20px 16px; }}
      .summary-bar {{ padding: 12px 16px; flex-wrap: wrap; }}
    }}
  </style>
</head>
<body>

<header>
  <a class="home-btn" href="../">&#8592; Home</a>
  <h1>Homework Dashboard</h1>
  <div class="meta">Last updated: {now_str} &nbsp;&bull;&nbsp; {len(courses)} subject{'s' if len(courses) != 1 else ''} &nbsp;&bull;&nbsp; {total_assignments} total assignment{'s' if total_assignments != 1 else ''}</div>
</header>

<div class="filter-bar">
  <button class="filter-btn active" data-filter="all">All</button>
  <button class="filter-btn" data-filter="overdue"><span class="dot" style="background:#991b1b"></span> Overdue (Last 3 Months)</button>
  <button class="filter-btn" data-filter="due-soon"><span class="dot" style="background:#d97706"></span> Due Soon</button>
  <button class="filter-btn" data-filter="upcoming"><span class="dot" style="background:#16a34a"></span> Upcoming</button>
  <button class="filter-btn" data-filter="turned-in"><span class="dot" style="background:#1d4ed8"></span> Turned In</button>
</div>

<div class="grid">
  {cards_html}
</div>

<footer>Click any assignment to open it in Google Classroom</footer>

<script>
  const filterBtns = document.querySelectorAll('.filter-btn');
  filterBtns.forEach(btn => {{
    btn.addEventListener('click', () => {{
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.dataset.filter;

      document.querySelectorAll('.card').forEach(card => {{
        const assignments = card.querySelectorAll('.assignment');
        let visible = 0;
        assignments.forEach(a => {{
          const show = filter === 'all' || a.dataset.filter === filter;
          a.style.display = show ? '' : 'none';
          if (show) visible++;
        }});
        card.classList.toggle('hidden', visible === 0);
      }});
    }});
  }});
</script>

</body>
</html>"""
    return html


def main():
    print("=== Google Classroom Homework Dashboard ===\n")

    creds = authenticate()
    service = build("classroom", "v1", credentials=creds)

    courses = fetch_data(service)

    if not courses:
        print("No courses found. Nothing to display.")
        return

    print(f"\nGenerating HTML page...")
    html = generate_html(courses)

    output_path = Path(OUTPUT_FILE).resolve()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved: {output_path}")
    print("Opening in browser...")
    webbrowser.open(output_path.as_uri())
    print("\nDone! Run this script again any time to refresh assignments.")


if __name__ == "__main__":
    main()
