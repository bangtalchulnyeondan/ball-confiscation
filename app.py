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

if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = None


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


def get_list(returned: bool):
    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json={
            "filter": {"property": "반환 완료", "checkbox": {"equals": returned}},
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


def mark_returned(page_id, returned: bool):
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json={"properties": {"반환 완료": {"checkbox": returned}}}
    )
    return r.status_code == 200


def delete_record(page_id):
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json={"archived": True}
    )
    return r.status_code == 200


def render_table(rows, show_return_btn=False, show_undo_btn=False):
    if show_undo_btn:
        h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([2, 2, 1, 2, 2, 2, 2, 2])
        h7.markdown("**되돌리기**")
    else:
        h1, h2, h3, h4, h5, h6, h8 = st.columns([2, 2, 1, 2, 2, 2, 2])
    h1.markdown("**이름**")
    h2.markdown("**학번**")
    h3.markdown("**횟수**")
    h4.markdown("**압수일**")
    h5.markdown("**반환예정일**")
    h6.markdown("**상태**")
    h8.markdown("**삭제**")
    st.divider()

    for row in rows:
        pid = row["page_id"]
        if show_undo_btn:
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 2, 1, 2, 2, 2, 2, 2])
        else:
            col1, col2, col3, col4, col5, col6, col8 = st.columns([2, 2, 1, 2, 2, 2, 2])
        col1.write(row["학생 이름"])
        col2.write(row["학번"])
        col3.write(f"{row['압수 횟수']}회")
        col4.write(row["압수 날짜"])
        col5.write(row["반환 예정일"])

        if show_return_btn:
            if col6.button("반환 완료", key=f"ret_{pid}"):
                if mark_returned(pid, True):
                    st.success(f"{row['학생 이름']} 반환 완료 처리됨")
                    st.rerun()
        else:
            col6.write("완료")

        if show_undo_btn:
            if col7.button("미반환으로", key=f"undo_{pid}"):
                if mark_returned(pid, False):
                    st.success(f"{row['학생 이름']} 미반환으로 변경됨")
                    st.rerun()

        # 삭제: 1단계 버튼 → 확인 메시지 표시
        if st.session_state.confirm_delete == pid:
            col8.warning("삭제하면 이 기록은 완전히 사라집니다.")
            c1, c2 = st.columns(2)
            if c1.button("확인 삭제", key=f"confirm_{pid}"):
                if delete_record(pid):
                    st.session_state.confirm_delete = None
                    st.success(f"{row['학생 이름']} 기록이 삭제됐습니다.")
                    st.rerun()
            if c2.button("취소", key=f"cancel_{pid}"):
                st.session_state.confirm_delete = None
                st.rerun()
        else:
            if col8.button("삭제", key=f"del_{pid}"):
                st.session_state.confirm_delete = pid
                st.rerun()


# ── UI ────────────────────────────────────────────

st.title("공 압수 기록")
tab1, tab2, tab3 = st.tabs(["압수 등록", "미반환 목록", "반환 완료 목록"])

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
    if st.button("새로고침", key="refresh_active"):
        st.rerun()
    rows = get_list(returned=False)
    if not rows:
        st.info("미반환 항목이 없습니다.")
    else:
        render_table(rows, show_return_btn=True, show_undo_btn=False)

with tab3:
    st.subheader("반환 완료 목록")
    if st.button("새로고침", key="refresh_returned"):
        st.rerun()
    rows = get_list(returned=True)
    if not rows:
        st.info("반환 완료 항목이 없습니다.")
    else:
        render_table(rows, show_return_btn=False, show_undo_btn=True)
