#!/usr/bin/env bash

redcap_notify_flatten_field() {
    printf '%s' "${1:-}" | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//'
}

redcap_notify_commit_count() {
    local commit_log="${1:-}"
    if [[ -z "$commit_log" || "$commit_log" == "(无法获取)" ]]; then
        echo "0"
        return 0
    fi
    printf '%s\n' "$commit_log" | awk 'NF {count++} END {print count+0}'
}

redcap_notify_latest_commit() {
    local commit_log="${1:-}"
    if [[ -z "$commit_log" || "$commit_log" == "(无法获取)" ]]; then
        return 0
    fi
    printf '%s\n' "$commit_log" | awk 'NF {print; exit}'
}

redcap_notify_commit_bullets() {
    local commit_log="${1:-}"
    if [[ -z "$commit_log" || "$commit_log" == "(无法获取)" ]]; then
        return 0
    fi
    printf '%s\n' "$commit_log" | awk 'NF {print "- " $0}'
}

redcap_build_completion_message() {
    local headline="${1:-RedCap Layer B 收尾完成}"
    local project="${2:-redcap}"
    local commit_log="${3:-}"
    local source_label report_label commit_count latest_commit bullet_list

    source_label=$(redcap_notify_flatten_field "${4:-}")
    report_label=$(redcap_notify_flatten_field "${5:-}")
    commit_count=$(redcap_notify_commit_count "$commit_log")
    latest_commit=$(redcap_notify_latest_commit "$commit_log")
    bullet_list=$(redcap_notify_commit_bullets "$commit_log")

    {
        printf '%s\n\n' "$headline"
        printf -- '- 项目：%s\n' "$project"
        [[ -n "$source_label" ]] && printf -- '- 来源：%s\n' "$source_label"
        [[ -n "$report_label" ]] && printf -- '- 任务报告：%s\n' "$report_label"
        if [[ "$commit_count" -gt 0 ]]; then
            printf -- '- 本轮提交数：%s\n' "$commit_count"
        fi
        [[ -n "$latest_commit" ]] && printf -- '- 最新提交：%s\n' "$latest_commit"
        if [[ -n "$bullet_list" ]]; then
            printf '\n**提交清单**\n%s\n' "$bullet_list"
        fi
    }
}
