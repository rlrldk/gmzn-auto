# GAMEZONE 자동 출석 (GitHub Actions)

gamezone.live 에 매일 자동으로 로그인 → 출석 페이지에 접속해서 출석을 처리한다.
내 PC가 꺼져 있어도 GitHub 서버가 cron 스케줄에 맞춰 돌려준다.

## 동작 원리

이 사이트는 Rhymix(구 XE) 기반이고, **로그인한 상태에서 `/attendance` 페이지를 열면
버튼 클릭 없이 자동으로 출석이 처리**되는 구조다. (출석부 글 제목이 전부 "자동출석입니다.")
그래서 스크립트는 "로그인 → 출석 페이지 GET" 만 하면 된다.

> GitHub Actions 는 매 실행마다 깨끗한 새 환경에서 돌아가므로 이전 로그인 세션이
> 남지 않는다. 따라서 매 실행마다 새로 로그인하는 것이 정상이고 가장 안정적이다.

## 공개 / 비공개 저장소

둘 다 가능하다.
- **공개(Public)**: Actions 실행시간 무제한. Secrets 는 공개여도 암호화되어 코드/로그에
  노출되지 않는다. (단, 코드 자체는 누구나 열람 가능 — 코드엔 비밀번호가 없으니 안전)
- **비공개(Private)**: 월 2,000분 무료. 이 작업은 하루 1~2회, 1분 남짓이라 한도에 한참 못 미친다.

> 참고: 스케줄이 예약 시각보다 늦게(수십 분~몇 시간) 도는 경우가 있는데, 그 **대기 시간은
> 사용량(분)에 포함되지 않는다.** 실제 실행 시간만 차감된다.

## 설정 방법

1. 이 폴더를 새 GitHub 저장소(공개/비공개 모두 가능)에 올린다.

   ```bash
   git init
   git add .
   git commit -m "gamezone 자동 출석"
   git branch -M main
   git remote add origin https://github.com/<내아이디>/<저장소>.git
   git push -u origin main
   ```

2. GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**
   에서 아래 두 개를 등록한다.

   | 이름 | 값 |
   |------|----|
   | `GAMEZONE_ID` | gamezone 로그인 아이디 |
   | `GAMEZONE_PW` | gamezone 로그인 비밀번호 |

3. 저장소 → **Actions** 탭 → 워크플로우 선택 → **Run workflow** 로 수동 실행해서
   로그가 `[SUCCESS] 출석 완료` 가 뜨는지 확인한다.

4. 확인되면 그 뒤로는 매일 자동 실행된다. (KST 00:10 / 09:10 두 번 시도)

## 로컬 테스트

```bash
pip install -r requirements.txt
set GAMEZONE_ID=내아이디
set GAMEZONE_PW=내비번
python attend.py
```

## 주의

- 비밀번호는 반드시 **GitHub Secrets** 로만 넣는다. 코드에 직접 적지 말 것.
- 공개 저장소여도 Secrets 는 노출되지 않지만, 코드 자체는 공개되므로 코드에 민감정보를 두지 않는다.
- 로그인이 실패하면(`[ERROR] 로그인 상태가 아닙니다`) 로그를 확인한다. 스크립트는
  로그인 폼의 hidden 필드를 자동으로 읽어 쓰므로, 폼 경로가 바뀌었다면 `LOGIN_PATH`
  환경변수(기본 `/index/login`)만 조정하면 된다.
