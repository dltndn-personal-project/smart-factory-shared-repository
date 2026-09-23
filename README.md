# Smart Factory Shared Contract

공통 계약 문서, Component 공통 작업 절차(`agent-core/`), Shared Issue 파일의 원본 저장소다. GitHub Issues 기능을 메시지 원본으로 사용하지 않는다.

| 경로 | 역할 |
|---|---|
| `docs/ARCHITECTURE.md` | 프로젝트 구조와 책임, 통합·릴리스 조건 |
| `docs/INTERFACES.md` | 통신 계약과 전환 규칙 |
| `docs/CONVENTIONS.md` | 공통 명명·시간·ID 규칙 |
| `docs/SHARED_WORKFLOW.md` | 메시지 등록·새 사실·답변 규칙 |
| `agent-core/` | 모든 Component가 `agent/core/`로 복사해 쓰는 작업 절차·도구의 원본. 각 Component는 `process_ref`로 채택한 commit과 일치하는지 CI로 검증한다 |
| `issues/index.json` | 본문을 읽기 전 조회하는 추가 전용 목록. 배열 순서가 검토 순서 |
| `issues/<ID>.yaml` | merge 후 불변인 메시지 원본 |
| `templates/` | 작성용 양식 |
| `issues/sample-*.yaml` | 운영 목록에서 제외된 가상 예시 |
| `.github/workflows/` | Shared PR의 색인·본문·추가 전용 규칙 검사, 새 MESSAGE PR 자동 승인 |
| `.github/CODEOWNERS` | Issue 추가 외 모든 변경의 승인 책임자 |

`docs/ARCHITECTURE.md`에 시스템 아키텍처가 작성되어 있고, `docs/INTERFACES.md`와 `docs/CONVENTIONS.md`는 `미정` 항목이 남은 초안이다. 내용을 확정한 뒤 Component가 사용할 commit을 선택한다. Component는 고정한 계약 commit의 문서와, 검토 시점 main commit의 Issue를 각각 조회한다. Issue ID나 `created_at`은 순서 기준이 아니다. 색인 배열의 앞에서부터 처리한다.

`agent-core/`를 바꾸는 PR도 계약 문서와 같이 DOCUMENT_CHANGE를 포함해야 하고, CODEOWNERS 승인 후 merge된다. merge된 DOCUMENT_CHANGE Issue가 모든 Component에 개선을 전파하는 메시지이며, 각 Component는 Shared 검토 때 `agent.py sync-core`로 채택한다(`agent-core/process/90-shared.md` 6·7절).

Component 등록부나 전파 자동화는 필요 없다. 실제 GitHub 저장소 이름은 자유이며, 각 Component의 `SHARED_CONFIG.json`에 연결한다. 이 저장소에는 자기 URL을 중복 설정하지 않는다.

## 검증

로컬에서는 `python3 -m pip install -r requirements.txt` 이후 `python3 scripts/validate_shared.py`로 현재 내용의 형식을 확인한다. 기존 내용의 불변성과 문서 변경에 대한 DOCUMENT_CHANGE 연결은 비교할 Git commit이 있어야 검사할 수 있으므로 `python3 scripts/validate_shared.py --base <기준 commit의 전체 SHA>`를 사용한다. 기준 commit의 색인이 비어 있으면 초기화 기간으로 보고 문서 변경에 DOCUMENT_CHANGE를 요구하지 않는다. 회귀 검사는 `python3 -m unittest discover -s scripts -p 'test_*.py'`와 `python3 -m unittest discover -s agent-core/tools -p 'test_*.py'`로 실행한다.

`.github/workflows/validate-shared.yml`은 PR과 main push에서 같은 검사를 수행한다. GitHub 저장소를 만든 뒤 main 브랜치의 보호 규칙에서 `Validate Shared / validate`를 필수 검사로 지정해야 실패한 PR의 merge를 막을 수 있다.

## 자동 승인

새 MESSAGE Issue와 `issues/index.json`만 바꾼 PR은 검사를 통과하면 워크플로가 승인하고 auto-merge(squash)를 켠다. 판정은 `scripts/auto_approval.py`가 하며 다음 중 하나라도 해당하면 자동 승인하지 않는다.

- 새 Issue 파일과 `issues/index.json` 외의 파일이 추가·수정·삭제됨 (`docs/`, 양식, 스크립트, 워크플로, 샘플 포함)
- 새 Issue 중 DOCUMENT_CHANGE가 있음
- 기준 commit의 `.github/CODEOWNERS`에 `*`의 실제 소유자가 지정되지 않음
- fork에서 온 PR 또는 draft PR

자동 승인되지 않은 PR은 CODEOWNERS 승인이 필요하다. 이 구분은 GitHub 설정이 있어야 강제된다.

1. `.github/CODEOWNERS`의 placeholder를 실제 계약 승인 책임자로 바꾼다.
2. Settings → Actions → General → Workflow permissions에서 "Allow GitHub Actions to create and approve pull requests"를 켠다.
3. Settings → General에서 "Allow auto-merge"와 "Allow squash merging"을 켠다.
4. main 브랜치 보호 규칙에서 PR 필수, 승인 1개 이상, "Require review from Code Owners", "Dismiss stale pull request approvals when new commits are pushed", 필수 검사 `Validate Shared / validate`를 지정하고 관리자 우회를 허용하지 않는다.

워크플로 자신을 고친 PR도 이 워크플로로 실행되므로 자동 승인 규칙 자체를 바꿀 수 있다. 그런 PR은 `.github/`가 CODEOWNERS 대상이라 봇 승인만으로 merge되지 않는다. CODEOWNERS 리뷰 설정이 자동 승인 안전성의 전제다. 워크플로 토큰으로 merge된 commit에서는 main push 검사가 다시 실행되지 않지만, 같은 검사가 PR에서 이미 필수로 통과했다.
