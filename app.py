import streamlit as st
import pandas as pd
import calendar
from datetime import date
from dotenv import load_dotenv
import os

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

st.set_page_config(page_title="Sanchu Scheduler", page_icon="🏥", layout="wide")

with open("styles.css") as f:
    st.markdown(
        f"<style>{f.read()}</style>",
        unsafe_allow_html=True
    )

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

CHIEF_PASSWORD = "sanchu123"

st.title("🏥 Sanchu Scheduler")
st.caption("AI-assisted residency scheduling dashboard")

if "requests" not in st.session_state:
    st.session_state.requests = pd.DataFrame(columns=[
        "Resident Name", "Request Type", "Start Date", "End Date", "Reason", "Status"
    ])

if "residents" not in st.session_state:
    st.session_state.residents = pd.DataFrame(columns=["Resident Name"])

if "draft_schedule" not in st.session_state:
    st.session_state.draft_schedule = pd.DataFrame(columns=[
        "Date", "Shift", "Assigned Resident", "Status"
    ])

if "posted_schedule" not in st.session_state:
    st.session_state.posted_schedule = pd.DataFrame(columns=[
        "Date", "Shift", "Assigned Resident"
    ])

if "month_offset" not in st.session_state:
    st.session_state.month_offset = 0

if "chief_logged_in" not in st.session_state:
    st.session_state.chief_logged_in = False


def chief_login():
    if not st.session_state.chief_logged_in:
        password = st.text_input("Chief Password", type="password")
        if st.button("Login"):
            if password == CHIEF_PASSWORD:
                st.session_state.chief_logged_in = True
                st.success("Logged in as Chief Resident.")
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()


def get_ai_response(question):
    if not GROQ_API_KEY:
        return "GROQ_API_KEY is missing from your .env file."

    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0.4,
        api_key=GROQ_API_KEY
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         """
         You are Sanchu Scheduler AI for a chief resident.
         Summarize requests, approved vacations, draft schedules, posted schedules,
         and possible conflicts. Do not invent data.
         Be practical and concise.
         """),
        ("human",
         """
         Question: {question}

         Requests:
         {requests}

         Draft Schedule:
         {draft}

         Posted Schedule:
         {posted}
         """)
    ])

    chain = prompt | llm | StrOutputParser()

    return chain.invoke({
        "question": question,
        "requests": st.session_state.requests.to_string(index=False),
        "draft": st.session_state.draft_schedule.to_string(index=False),
        "posted": st.session_state.posted_schedule.to_string(index=False)
    })


def is_resident_available(resident, shift_date):
    approved = st.session_state.requests[
        (st.session_state.requests["Resident Name"] == resident) &
        (st.session_state.requests["Status"] == "Approved")
    ]

    for _, row in approved.iterrows():
        start = pd.to_datetime(row["Start Date"]).date()
        end = pd.to_datetime(row["End Date"]).date()
        if start <= shift_date <= end:
            return False

    return True


def generate_draft_schedule(year, month):
    residents = st.session_state.residents["Resident Name"].dropna().tolist()

    if not residents:
        return pd.DataFrame(columns=["Date", "Shift", "Assigned Resident", "Status"])

    shifts = ["Day", "Night"]
    days_in_month = calendar.monthrange(year, month)[1]

    draft_rows = []
    resident_index = 0

    for day_num in range(1, days_in_month + 1):
        shift_date = date(year, month, day_num)

        for shift in shifts:
            assigned = None
            attempts = 0

            while attempts < len(residents):
                possible_resident = residents[resident_index % len(residents)]
                resident_index += 1
                attempts += 1

                if is_resident_available(possible_resident, shift_date):
                    assigned = possible_resident
                    break

            if assigned is None:
                assigned = "NEEDS COVERAGE"

            draft_rows.append({
                "Date": str(shift_date),
                "Shift": shift,
                "Assigned Resident": assigned,
                "Status": "Draft"
            })

    return pd.DataFrame(draft_rows)


page = st.sidebar.radio(
    "Navigation",
    [
        "Public Schedule",
        "Submit Request",
        "Chief Dashboard",
        "Generate Draft Schedule",
        "Chief Approval",
        "AI Assistant"
    ]
)


if page == "Public Schedule":
    st.header("Public Posted Schedule")

    today = date.today()
    month = today.month + st.session_state.month_offset
    year = today.year

    while month > 12:
        month -= 12
        year += 1

    while month < 1:
        month += 12
        year -= 1

    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        if st.button("⬅ Previous Month"):
            st.session_state.month_offset -= 1
            st.rerun()

    with col2:
        st.subheader(f"{calendar.month_name[month]} {year}")

    with col3:
        if st.button("Next Month ➡"):
            st.session_state.month_offset += 1
            st.rerun()

    if st.session_state.posted_schedule.empty:
        st.info("No public schedule has been posted yet.")
    else:
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdatescalendar(year, month)

        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        cols = st.columns(7)

        for i, d in enumerate(days):
            cols[i].markdown(f"**{d}**")

        for week in month_days:
            cols = st.columns(7)

            for i, day in enumerate(week):
                with cols[i]:
                    if day.month == month:
                        st.markdown(f"### {day.day}")

                        day_schedule = st.session_state.posted_schedule[
                            st.session_state.posted_schedule["Date"] == str(day)
                        ]

                        for _, row in day_schedule.iterrows():
                            st.write(f"**{row['Shift']}**")
                            st.caption(row["Assigned Resident"])


elif page == "Submit Request":
    st.header("Submit Vacation / Schedule Request")

    with st.form("request_form"):
        name = st.text_input("Resident Name")
        request_type = st.selectbox(
            "Request Type",
            ["Vacation", "Day Off", "Conference", "Sick Leave", "Shift Swap", "Other"]
        )
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")
        reason = st.text_area("Reason / Notes")

        submitted = st.form_submit_button("Submit Request")

        if submitted:
            if not name.strip():
                st.error("Please enter your name.")
            elif end_date < start_date:
                st.error("End date cannot be before start date.")
            else:
                new_request = pd.DataFrame([{
                    "Resident Name": name.strip(),
                    "Request Type": request_type,
                    "Start Date": str(start_date),
                    "End Date": str(end_date),
                    "Reason": reason,
                    "Status": "Pending"
                }])

                st.session_state.requests = pd.concat(
                    [st.session_state.requests, new_request],
                    ignore_index=True
                )

                if name.strip() not in st.session_state.residents["Resident Name"].tolist():
                    new_resident = pd.DataFrame([{"Resident Name": name.strip()}])
                    st.session_state.residents = pd.concat(
                        [st.session_state.residents, new_resident],
                        ignore_index=True
                    )

                st.success("Request submitted. Status: Pending.")


elif page == "Chief Dashboard":
    chief_login()

    st.header("Chief Resident Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Pending Requests", len(st.session_state.requests[st.session_state.requests["Status"] == "Pending"]))
    col2.metric("Approved Requests", len(st.session_state.requests[st.session_state.requests["Status"] == "Approved"]))
    col3.metric("Denied Requests", len(st.session_state.requests[st.session_state.requests["Status"] == "Denied"]))
    col4.metric("Residents", len(st.session_state.residents))

    st.subheader("All Requests")
    st.dataframe(st.session_state.requests, use_container_width=True)

    st.subheader("Residents")
    edited_residents = st.data_editor(
        st.session_state.residents,
        num_rows="dynamic",
        use_container_width=True
    )
    st.session_state.residents = edited_residents


elif page == "Chief Approval":
    chief_login()

    st.header("Approve / Deny Resident Requests")

    if st.session_state.requests.empty:
        st.info("No requests yet.")
    else:
        for i, row in st.session_state.requests.iterrows():
            with st.expander(f"{row['Resident Name']} - {row['Request Type']} - {row['Status']}"):
                st.write(f"**Start:** {row['Start Date']}")
                st.write(f"**End:** {row['End Date']}")
                st.write(f"**Reason:** {row['Reason']}")

                col1, col2, col3 = st.columns(3)

                if col1.button("Approve", key=f"approve_{i}"):
                    st.session_state.requests.at[i, "Status"] = "Approved"
                    st.rerun()

                if col2.button("Deny", key=f"deny_{i}"):
                    st.session_state.requests.at[i, "Status"] = "Denied"
                    st.rerun()

                if col3.button("Pending", key=f"pending_{i}"):
                    st.session_state.requests.at[i, "Status"] = "Pending"
                    st.rerun()


elif page == "Generate Draft Schedule":
    chief_login()

    st.header("Generate Draft Monthly Schedule")

    today = date.today()
    selected_year = st.number_input("Year", min_value=2026, max_value=2035, value=today.year)
    selected_month = st.selectbox(
        "Month",
        list(range(1, 13)),
        index=today.month - 1,
        format_func=lambda x: calendar.month_name[x]
    )

    st.warning("This creates a DRAFT schedule only. It will not be public until approved and posted.")

    if st.button("Generate Draft Schedule"):
        st.session_state.draft_schedule = generate_draft_schedule(
            int(selected_year),
            int(selected_month)
        )
        st.success("Draft schedule generated. Review before posting.")

    st.subheader("Draft Schedule")

    if st.session_state.draft_schedule.empty:
        st.info("No draft schedule generated yet.")
    else:
        edited_draft = st.data_editor(
            st.session_state.draft_schedule,
            num_rows="dynamic",
            use_container_width=True
        )
        st.session_state.draft_schedule = edited_draft

        needs_coverage = st.session_state.draft_schedule[
            st.session_state.draft_schedule["Assigned Resident"] == "NEEDS COVERAGE"
        ]

        if not needs_coverage.empty:
            st.error("Some shifts need coverage before posting.")
            st.dataframe(needs_coverage, use_container_width=True)

        if st.button("Approve and Post Draft Schedule"):
            if needs_coverage.empty:
                st.session_state.posted_schedule = st.session_state.draft_schedule[
                    ["Date", "Shift", "Assigned Resident"]
                ].copy()

                st.session_state.draft_schedule["Status"] = "Posted"
                st.success("Draft approved and posted publicly.")
            else:
                st.error("Fix NEEDS COVERAGE shifts before posting.")


elif page == "AI Assistant":
    chief_login()

    st.header("Sanchu AI Assistant")

    st.caption("Ask: summarize pending requests, find conflicts, who is unavailable, or review the draft schedule.")

    user_question = st.chat_input("Ask Sanchu AI...")

    if user_question:
        with st.chat_message("user"):
            st.write(user_question)

        with st.chat_message("assistant"):
            with st.spinner("Sanchu AI is reviewing the schedule..."):
                answer = get_ai_response(user_question)
                st.write(answer)