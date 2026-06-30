#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GAMEZONE (gamezone.live) 자동 출석 스크립트
- Rhymix(구 XE) 기반 사이트에 로그인 후 출석 페이지에 접속하면
  버튼 클릭 없이 자동으로 출석이 처리되는 구조를 이용한다.
- GitHub Actions cron으로 매일 실행하는 것을 전제로 작성.

필요한 환경변수(=GitHub Secrets):
  GAMEZONE_ID  : 로그인 아이디
  GAMEZONE_PW  : 로그인 비밀번호
선택:
  GAMEZONE_BASE: 기본 주소 (기본값 http://gamezone.live)
  LOGIN_PATH   : 로그인 폼 경로 (기본값 /index/login)
"""

import os
import re
import sys
import requests

BASE = os.environ.get("GAMEZONE_BASE", "http://gamezone.live").rstrip("/")
USER_ID = os.environ.get("GAMEZONE_ID")
PASSWORD = os.environ.get("GAMEZONE_PW")
# 로그인 폼이 있는 경로. 어떤 mid 든 로그인 자체는 동작하므로 기본 /index/login 사용.
LOGIN_PATH = os.environ.get("LOGIN_PATH", "/index/login")

LOGIN_FORM_URL = f"{BASE}{LOGIN_PATH if LOGIN_PATH.startswith('/') else '/' + LOGIN_PATH}"
ATTEND_URL = f"{BASE}/attendance"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def log(msg):
    print(msg, flush=True)


def get_csrf_token(session, html):
    """페이지 HTML 또는 쿠키에서 Rhymix CSRF 토큰을 찾는다."""
    # 1) meta 태그
    m = re.search(r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    # 2) 폼 내부 hidden input
    m = re.search(r'name=["\']_rx_csrf_token["\']\s+value=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    # 3) 쿠키
    for key in ("_rx_csrf_token", "rx_csrf_token"):
        if key in session.cookies:
            return session.cookies.get(key)
    return None


def extract_login_form(html):
    """로그인 폼(act=procMemberLogin)을 찾아 그 안의 모든 input(name=value)을 dict 로 반환."""
    # procMemberLogin 이 들어있는 <form> ... </form> 블록을 찾는다.
    forms = re.findall(r"<form\b[^>]*>(.*?)</form>", html, re.I | re.S)
    target = None
    for inner in forms:
        if "procMemberLogin" in inner:
            target = inner
            break
    if target is None:
        return {}

    fields = {}
    for m in re.finditer(r"<input\b[^>]*>", target, re.I):
        tag = m.group(0)
        name_m = re.search(r'name=["\']([^"\']+)["\']', tag, re.I)
        if not name_m:
            continue
        value_m = re.search(r'value=["\']([^"\']*)["\']', tag, re.I)
        fields[name_m.group(1)] = value_m.group(1) if value_m else ""
    return fields


def login(session):
    if not USER_ID or not PASSWORD:
        log("[ERROR] GAMEZONE_ID / GAMEZONE_PW 환경변수가 없습니다.")
        sys.exit(1)

    # 로그인 폼 페이지에서 쿠키 + 폼 필드(mid, ruleset, csrf 등) 확보
    r = session.get(LOGIN_FORM_URL, timeout=30)
    r.encoding = "utf-8"

    # 폼의 hidden 필드를 그대로 가져와서 그 위에 자격증명만 덮어쓴다.
    data = extract_login_form(r.text)
    if not data:
        log("[WARN] 로그인 폼을 찾지 못해 기본 파라미터로 시도합니다.")
        data = {"act": "procMemberLogin", "mid": "index", "ruleset": "@login"}

    token = data.get("_rx_csrf_token") or get_csrf_token(session, r.text)
    log(f"[INFO] 로그인 폼 필드: {sorted(data.keys())}")
    log(f"[INFO] CSRF token: {'확보' if token else '없음(계속 시도)'}")

    # 자격증명 주입 (폼 값보다 우선)
    data["act"] = "procMemberLogin"
    data["user_id"] = USER_ID
    data["password"] = PASSWORD
    data["keep_signed"] = "Y"
    if token:
        data["_rx_csrf_token"] = token

    # Rhymix rx_ajax 로그인은 XHR 요청으로 처리되고 JSON 으로 응답한다.
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": LOGIN_FORM_URL,
    }
    if token:
        headers["X-CSRF-Token"] = token

    r = session.post(BASE + "/", data=data, headers=headers, timeout=30)
    r.encoding = "utf-8"
    body = r.text

    # rx_ajax 응답은 보통 {"error":0,...} 형태의 JSON
    if ('"error":0' in body) or ('"error": 0' in body) or ("<error>0</error>" in body):
        log("[INFO] 로그인 성공 응답 확인.")
    elif r.status_code in (200, 302):
        log("[INFO] 로그인 요청 전송 완료(응답 형식 확인 필요).")
    else:
        log(f"[WARN] 로그인 응답이 예상과 다릅니다. status={r.status_code}")
    # 에러 메시지가 있으면 일부 출력 (비밀번호는 포함되지 않음)
    m_msg = re.search(r'"message"\s*:\s*"([^"]+)"', body)
    if m_msg:
        log(f"[INFO] 서버 메시지: {m_msg.group(1)}")
    return session


def check_logged_in(html):
    # 로그아웃 링크가 보이면 로그인 상태로 판단
    return ("dispMemberLogout" in html) or ("로그아웃" in html)


def attend(session):
    r = session.get(ATTEND_URL, timeout=30)
    r.encoding = "utf-8"
    html = r.text

    if not check_logged_in(html):
        log("[ERROR] 로그인 상태가 아닙니다. 아이디/비밀번호 또는 로그인 방식을 확인하세요.")
        log(html[:500])
        sys.exit(1)

    if "출석이 완료" in html or "출첵완료" in html:
        log("[SUCCESS] 출석 완료 (이미 출석했거나 방금 출석됨).")
    elif "출석가능" in html:
        log("[INFO] 출석 가능 상태 표시됨. 페이지 접속으로 출석 처리되었을 가능성이 높습니다.")
    else:
        log("[WARN] 출석 상태를 확정하지 못했습니다. 응답 일부를 출력합니다.")
        snippet = re.sub(r"\s+", " ", html)
        idx = snippet.find("출석")
        log(snippet[max(0, idx - 100): idx + 300] if idx >= 0 else snippet[:400])


def main():
    log(f"[INFO] 대상: {BASE}")
    with requests.Session() as session:
        session.headers.update({"User-Agent": UA})
        login(session)
        attend(session)


if __name__ == "__main__":
    main()
