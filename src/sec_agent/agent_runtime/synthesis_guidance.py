"""Role ownership for existing native final-author paths; no extra model loop."""


def final_author_guidance(options):
    if not (options.get('native_model_transition') or options.get('research_delegate')):
        return ''
    return (
        '\n最终综合责任：你现在对原题的完整答案负责，不只是编辑旧作者或落实审稿清单。'
        '先用 read_current_report(field="synthesis_context") 取得当前稿版本、意见处理及依据回读入口，'
        '结合现有工作笔记重新判断现在能回答什么、哪些解释撤回、哪些结论仍有依据。'
        '旧标题、章节、观点排序和投资建议均可重写，不预设保留旧故事，也不为换作者重做已成功调查。'
        '替代解释必须独立经受证据检验，不能只删掉原错误并生成另一条未经验证的总括。'
        '必要时亲自补证；对自己此前的复核意见同样可以纠正。'
        '保存并交付你承担责任的最终稿，不再转交原作者润色。原生会话转换不等于研究质量通过。'
    )
