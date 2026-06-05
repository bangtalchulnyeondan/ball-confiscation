import streamlit as st
import requests
from datetime import datetime, timedelta

TOKEN = st.secrets["NOTION_TOKEN"]
DB_ID = st.secrets["DB_ID"]
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

CONFISCATION_DAYS = {1: 14, 2: 30, 3: 60}


def get_confiscation_count(student_id):
    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={"filter": {"property": "학번", "rich_text": {"equals": student_id}}}
    )
    return len(r.json().get("results", []))


def register(student_name, student_id, confiscation_date):
    count = get_confiscation_count(student_id) + 1
    days = CONFISCATION_DAYS.get(count, 60)
    return_date = confiscation_date + timedelta(days=days)

    data = {
        "parent": {"database_id": DB_ID},
        "properties": {
            "학생 이름": {"title": [{"type": "text", "text": {"content": student_name}}]},
            "학번": {"rich_text": [{"type": "text", "text": {"content": student_id}}]},
            "압수 횟수": {"number": count},
            "압수 날짜": {"date": {"start": confiscation_date.strftime("%Y-%m-%d")}},
            "반환 예정일": {"date": {"start": return_date.strftime("%Y-%m-%d")}},
            "반환 완료": {"checkbox": False}
        }
    }
    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=data)
    return r.status_code == 200, count, days, return_date


def get_active_list():
    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={
            "filter": {"property": "반환 완료", "checkbox": {"equals": False}},
            "sorts": [{"property": "반환 예정일", "direction": "ascending"}]
        }
    )
    rows = []
    for p in r.json().get("results", []):
        props = p["properties"]
        rows.append({
            "page_id": p["id"],
            "학생 이름": props["학생 이름"]["title"][0]["plain_text"] if props["학생 이름"]["title"] else "",
            "학번": props["학번"]["rich_text"][0]["plain_text"] if props["학번"]["rich_text"] else "",
            "압수 횟수": props["압수 횟수"]["number"] or 0,
            "압수 날짜": props["압수 날짜"]["date"]["start"] if props["압수 날짜"]["date"] else "",
            "반환 예정일": props["반환 예정일"]["date"]["start"] if props["반환 예정일"]["date"] else "",
        })
    return rows


def mark_returned(page_id):
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json={"properties": {"반환 완료": {"checkbox": True}}}
    )
    return r.status_code == 200


# ── UI ────────────────────────────────────────────

st.title("공 압수 기록")
tab1, tab2 = st.tabs(["압수 등록", "미반환 목록"])

with tab1:
    st.subheader("압수 등록")
    with st.form("register_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("학생 이름")
            student_id = st.text_input("학번 (예: 20601)")
        with col2:
            conf_date = st.date_input("압수 날짜", value=datetime.today())
        submitted = st.form_submit_button("등록")

    if submitted:
        if not name or not student_id:
            st.error("학생 이름과 학번을 입력해주세요.")
        else:
            ok, count, days, return_date = register(name, student_id, conf_date)
            if ok:
                st.success(f"등록 완료! {name} ({student_id}) — {count}회 압수 / {days}일 / 반환 예정일: {return_date.strftime('%Y-%m-%d')}")
            else:
                st.error("등록 실패. 다시 시도해주세요.")

with tab2:
    st.subheader("미반환 목록")
    if st.button("새로고침"):
        st.rerun()

    rows = get_active_list()
    if not rows:
        st.info("미반환 항목이 없습니다.")
    else:
        for row in rows:
            col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 1, 2, 2, 2])
            col1.write(row["학생 이름"])
            col2.write(row["학번"])
            col3.write(f"{row['압수 횟수']}회")
            col4.write(row["압수 날짜"])
            col5.write(row["반환 예정일"])
            if col6.button("반환 완료", key=row["page_id"]):
                if mark_returned(row["page_id"]):
                    st.success(f"{row['학생 이름']} 반환 완료 처리됨")
                    st.rerun()
