# Shared 게시판 운영

## 원본과 읽기

`docs/`는 계약, `issues/`는 변경·소통 이력이다. 각 Component는 GitHub API로 조회하고 자신의 처리 상태만 로컬에 기록한다. `issues/index.json`의 배열 순서가 공식 검토 순서다. Issue merge는 게시 완료이며 수신·검토·구현 완료를 뜻하지 않는다.

## 등록

`issues/sample-*.yaml`은 같은 폴더에 둔 예시이며 운영 색인에 등록하지 않는다. 샘플 ID는 가상 값이다. 실제 게시할 때는 새 `ISSUE-<UUID>`와 실제 근거를 작성하고, 샘플 ID를 운영 Issue에서 참조하지 않는다. 샘플은 편집할 수 있으며 merge된 운영 Issue의 불변성 규칙을 적용하지 않는다.

1. MESSAGE 또는 DOCUMENT_CHANGE 양식을 복사한다. 두 유형 모두 동일한 필드 이름을 사용한다.
2. `ISSUE-<UUID>`를 새 ID로 발급한다. 예: `uuidgen` 결과를 붙인다. ID나 시간은 순서를 뜻하지 않는다.
3. `issues/<ID>.yaml`에 저장하고 `issues/index.json`의 `issues` 배열에 다음 항목을 추가한다.

```json
{
  "issue_id": "ISSUE-<UUID>",
  "type": "MESSAGE",
  "summary": "확인이 필요한 관찰 결과",
  "attention": ["producer"],
  "path": "issues/ISSUE-<UUID>.yaml"
}
```

4. 문서를 바꾸면 DOCUMENT_CHANGE에 변경 경로·이유·호환성을 적고 같은 PR에 문서와 색인을 포함한다. 색인의 기존 항목은 수정·재배열·삭제하지 않고 새 항목을 끝에 추가한다. 다른 PR과 충돌하면 최신 main을 기준으로 다시 정렬하여 양쪽 새 항목을 모두 뒤에 남긴다.
5. Shared 저장소의 작업 브랜치에서 PR을 작성한다. merge 전에는 공식 계약이나 게시된 메시지로 취급하지 않는다.

`source.component`, `source.task`, `summary`, `created_at`(UTC ISO-8601), `attention`, `related_issues`는 공통 필드다. `attention: []`는 특정 대상 지정이 없다는 뜻이다. `related_issues`는 이미 게시된 앞선 Issue만 가리킨다. MESSAGE의 `observation`, `requested_action`, `evidence`와 DOCUMENT_CHANGE의 변경 내역을 충분히 작성한다. 해당 없는 요청·증거는 각각 null·빈 배열로 둔다.

## API로 게시할 때

조회와 달리 게시에는 쓰기 권한이 필요하다. 기존 인증을 사용하고 토큰을 파일에 기록하지 않는다. 사용자가 게시를 요청한 범위에서 다음 순서로 진행한다.

1. 저장소 기본 브랜치와 현재 head commit을 API로 확인한다.
2. 고유한 작업 브랜치를 만들고 그 head를 기준으로 Issue·색인·필요한 문서를 준비한다.
3. 여러 파일 변경은 Git Data API의 blob → tree(`base_tree` 지정) → commit(`parents` 지정) → 작업 브랜치 ref 갱신으로 한 commit에 담는다. ref는 force 없이 갱신한다.
4. Pulls API로 기본 브랜치를 대상으로 PR을 만든다. 응답의 PR URL을 작업 결과에 남긴다. Agent가 merge하거나 auto-merge를 켜지 않는다. 새 MESSAGE만 추가한 PR은 CI가 통과하면 워크플로가 승인·merge하고, DOCUMENT_CHANGE와 그 외 변경은 CODEOWNERS 승인 후 merge된다. PR 생성은 게시 완료가 아니므로 merge 여부를 확인하여 보고한다.
5. 응답이 불명확하거나 실패하면 branch·commit·기존 PR을 먼저 조회한다. 새 ID나 중복 PR을 무조건 만들지 않는다.

요청 본문은 JSON 파일로 작성하여 `gh api --input <파일>`로 전달한다. Issue 본문을 shell 명령 문자열에 삽입하지 않는다. GitHub 저장소가 연결되지 않았거나 게시 권한이 없으면 초안을 유지하고 게시 미완료를 보고한다.

## 답변과 새 사실

- 단순한 no_impact는 Component에만 기록한다.
- 상대의 다음 행동에 필요한 결과·버전·검증 요청은 새 MESSAGE로 게시하고 `related_issues`로 원본을 연결한다.
- 이미 게시된 내용을 바꾸지 않는다. 나중에 확인한 사실은 새 Issue에 기록한다. 앞선 Issue와 관계가 있으면 `related_issues`를 사용한다. 수신 Component는 뒤의 Issue를 만났을 때 새 사실에 따라 자신의 처리 결과를 다시 판단할 수 있다.
- 확인이나 해결을 요청하는 MESSAGE는 `follow_up.owner`와 `follow_up.done_when`을 적는다. 이는 요청된 추적 책임이며, 수신자의 수락이나 영향 판단을 대신하지 않는다.
- Component의 `applied`는 그 Component의 조치 완료다. 전체 해결은 관련 Component와 Integration의 증거를 확인한 후 후속 MESSAGE로 알린다.

## agent-core 변경

`agent-core/`는 모든 Component가 `agent/core/`로 복사해 쓰는 작업 절차와 도구다. Component의 회고에서 원인이 PROCESS로 반복되면 그 Component의 Agent가 변경을 제안한다.

1. `agent-core/`의 파일을 고치고, 도구를 바꾸면 테스트도 고친다.
2. DOCUMENT_CHANGE의 `changed_documents`에 바꾼 `agent-core/` 경로를 적는다. `attention: []`(모든 Component), `reason`에 근거 회고 ID, `transition.adoption`에 sync-core 채택, `rollback`에 이전 `process_ref`로 복구를 적는다.
3. CODEOWNERS 승인 후 merge된다. merge된 DOCUMENT_CHANGE가 전파 메시지다. 별도 MESSAGE를 게시하지 않는다.
4. 각 Component는 Shared 검토에서 이 Issue를 만나면 `agent.py sync-core --ref <review_sha>`로 채택하고 처리 상태를 기록한다.

## 유지 관리

색인은 소량 메타데이터의 중복이지만 본문 전체 다운로드를 피하기 위해 유지한다. 같은 PR에서 수동으로 갱신하며 CI가 본문과의 일치, 누락, 순서와 기존 Issue의 불변성을 검사한다. 검색 서버·알림은 이 템플릿에 포함하지 않는다.

Issue가 많아져 목록 크기가 실제 문제가 되면 연도별 색인 등으로 확장한다. 기존 ID와 참조 경로를 보존하고 조회 절차도 함께 변경한다. 처리 완료를 이유로 원본을 삭제하지 않는다.

API 참고: [gh api](https://cli.github.com/manual/gh_api), [Contents API](https://docs.github.com/en/rest/repos/contents), [Git Data API](https://docs.github.com/en/rest/git), [Pulls API](https://docs.github.com/en/rest/pulls/pulls).
