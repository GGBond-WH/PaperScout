"""
UI Components for OpenReview Paper Filtering Tool.
Reusable Streamlit components for the application.
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional
from config import (
    get_available_venues,
    MIN_YEAR,
    MAX_YEAR,
    DEFAULT_PAGE_SIZE,
    MAX_DISPLAY_RESULTS,
)
from parsing import highlight_keywords, parse_keywords_input


def render_sidebar_filters(max_score_in_dataset: Optional[float] = None) -> Dict[str, Any]:
    """
    Render all sidebar filter widgets.
    
    Args:
        max_score_in_dataset: Maximum score found in the loaded dataset (for adaptive scaling)
        
    Returns:
        Dictionary containing all filter settings
    """
    st.sidebar.header("🔍 筛选条件")
    
    # ---- Venue Selection ----
    st.sidebar.subheader("会议选择")
    
    available_venues = get_available_venues()
    selected_venues = st.sidebar.multiselect(
        "选择会议（可多选）",
        options=available_venues,
        default=["ICLR"],
        help="支持别名：如输入 nips 会自动识别为 NeurIPS"
    )
    
    # Custom venue input
    custom_venue = st.sidebar.text_input(
        "自定义 Venue ID（可选）",
        placeholder="例如: ICLR.cc/2024/Conference",
        help="直接输入 OpenReview 的 venue/group ID"
    )
    
    # ---- Year Selection ----
    st.sidebar.subheader("年份筛选")
    
    year_range = st.sidebar.slider(
        "年份范围",
        min_value=MIN_YEAR,
        max_value=MAX_YEAR,
        value=(2024, 2024),
        help="选择要查询的年份范围"
    )
    
    # ---- Keyword Filters ----
    st.sidebar.subheader("关键词筛选")
    
    keywords_input = st.sidebar.text_input(
        "关键词",
        placeholder="transformer attention（空格或逗号分隔）",
        help="输入一个或多个关键词，用空格或逗号分隔"
    )
    
    keyword_logic = st.sidebar.radio(
        "关键词逻辑",
        options=["OR", "AND"],
        horizontal=True,
        help="OR: 匹配任意关键词; AND: 匹配所有关键词"
    )
    
    field_scope = st.sidebar.selectbox(
        "匹配范围",
        options=[
            ("title_or_abstract", "标题或摘要"),
            ("title", "仅标题"),
            ("abstract", "仅摘要"),
            ("title_and_abstract", "标题且摘要都要匹配"),
        ],
        format_func=lambda x: x[1],
        help="选择关键词搜索的范围"
    )
    
    # ---- Score Filters ----
    st.sidebar.subheader("评分筛选")
    
    # Adaptive scaling logic
    is_5_point_scale = False
    max_slider_value = 10.0
    
    if max_score_in_dataset is not None:
        # Debug: show detected max score
        # st.sidebar.caption(f"Debug: Detected max score = {max_score_in_dataset}")
        
        # Heuristic: if max score is <= 5.5, assume 5-point scale (NeurIPS 2025 style)
        if 0 < max_score_in_dataset <= 5.5:
            is_5_point_scale = True
            max_slider_value = 5.0
            st.sidebar.info(f"⚠️ 检测到此会议最大评分为 {max_score_in_dataset:.1f} (疑为5分制)，已自动调整筛选范围。")
        elif max_score_in_dataset > 5.5:
             # Just to be sure, show if it's high
             pass
    
    # Helper to prevent error if session state has value > max_slider_value
    def clamp_session_value(key, max_val):
        if key in st.session_state and st.session_state[key] > max_val:
            st.session_state[key] = 0.0
            
    # Clamp values for all score inputs
    clamp_session_value('min_avg_score_input', max_slider_value)
    clamp_session_value('min_max_score_input', max_slider_value)
    
    min_avg_score = st.sidebar.number_input(
        f"最低平均分 (avg_score ≥) - 上限 {max_slider_value}",
        min_value=0.0,
        max_value=max_slider_value,
        value=0.0 if not is_5_point_scale else min(st.session_state.get('min_avg_score_input', 0.0), max_slider_value),
        step=0.5,
        help="筛选平均评分大于等于此值的论文",
        key='min_avg_score_input'
    )
    
    min_max_score = st.sidebar.number_input(
        f"最低最高分 (max_score ≥) - 上限 {max_slider_value}",
        min_value=0.0,
        max_value=max_slider_value,
        value=0.0 if not is_5_point_scale else min(st.session_state.get('min_max_score_input', 0.0), max_slider_value),
        step=0.5,
        help="筛选最高评分大于等于此值的论文",
        key='min_max_score_input'
    )
    
    min_review_count = st.sidebar.number_input(
        "最少评审数 (scored_review_count ≥)",
        min_value=0,
        max_value=10,
        value=0,
        step=1,
        help="筛选至少有N个有效评分的论文"
    )
    
    # Optional: confidence filter
    with st.sidebar.expander("高级筛选（置信度）"):
        min_confidence = st.number_input(
            "最低平均置信度",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.5,
            help="筛选评审置信度（如果有的话）"
        )
    
    # Quick filter for reviewed papers only
    only_reviewed = st.sidebar.checkbox(
        "只显示有评审的论文",
        value=True,
        help="勾选后只显示有评分记录的论文，加快筛选速度"
    )
    
    # ---- Sorting ----
    st.sidebar.subheader("排序")
    
    sort_options = [
        ("avg_score", "平均分 (高→低)"),
        ("max_score", "最高分 (高→低)"),
        ("scored_review_count", "评审数 (多→少)"),
        ("year", "年份 (新→旧)"),
        ("title", "标题字母序"),
    ]
    
    sort_by = st.sidebar.selectbox(
        "排序方式",
        options=sort_options,
        format_func=lambda x: x[1],
    )
    
    # ---- Display Settings ----
    st.sidebar.subheader("显示设置")
    
    page_size = st.sidebar.selectbox(
        "每页显示数量",
        options=[20, 50, 100, 200],
        index=1,
    )
    
    # Parse keywords
    keywords = parse_keywords_input(keywords_input)
    
    return {
        "venues": selected_venues,
        "custom_venue": custom_venue.strip(),
        "year_start": year_range[0],
        "year_end": year_range[1],
        "keywords": keywords,
        "keyword_logic": keyword_logic,
        "field_scope": field_scope[0],
        "min_avg_score": min_avg_score if min_avg_score > 0 else None,
        "min_max_score": min_max_score if min_max_score > 0 else None,
        "min_review_count": min_review_count if min_review_count > 0 else None,
        "min_confidence": min_confidence if min_confidence > 0 else None,
        "only_reviewed": only_reviewed,
        "sort_by": sort_by[0],
        "page_size": page_size,
    }


def render_filter_summary(filters: Dict[str, Any], result_count: int, total_count: int):
    """
    Display current filter summary and result count.
    """
    cols = st.columns([3, 1])
    
    with cols[0]:
        summary_parts = []
        
        if filters["venues"]:
            summary_parts.append(f"**会议**: {', '.join(filters['venues'])}")
        if filters["custom_venue"]:
            summary_parts.append(f"**自定义**: {filters['custom_venue']}")
        
        summary_parts.append(f"**年份**: {filters['year_start']}-{filters['year_end']}")
        
        if filters["keywords"]:
            kw_str = ", ".join(filters["keywords"])
            summary_parts.append(f"**关键词**: {kw_str} ({filters['keyword_logic']})")
        
        if filters["min_avg_score"]:
            summary_parts.append(f"**平均分≥**: {filters['min_avg_score']}")
        if filters["min_max_score"]:
            summary_parts.append(f"**最高分≥**: {filters['min_max_score']}")
        
        st.markdown(" | ".join(summary_parts))
    
    with cols[1]:
        st.metric("匹配结果", f"{result_count} / {total_count}")


def render_paper_table(
    papers: List[Dict[str, Any]], 
    page: int, 
    page_size: int,
    keywords: List[str] = None,
) -> None:
    """
    Render paginated paper table with expandable details.
    """
    if not papers:
        st.info("没有找到匹配的论文。请调整筛选条件。")
        return
    
    # Pagination
    total_papers = len(papers)
    total_pages = (total_papers + page_size - 1) // page_size
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, total_papers)
    page_papers = papers[start_idx:end_idx]
    
    # Page navigation
    if total_pages > 1:
        cols = st.columns([1, 3, 1])
        with cols[0]:
            if st.button("◀ 上一页", disabled=page == 0):
                st.session_state.current_page = page - 1
                st.rerun()
        with cols[1]:
            st.markdown(f"<center>第 {page + 1} / {total_pages} 页 (共 {total_papers} 条)</center>", unsafe_allow_html=True)
        with cols[2]:
            if st.button("下一页 ▶", disabled=page >= total_pages - 1):
                st.session_state.current_page = page + 1
                st.rerun()
    
    # Create summary dataframe
    df_data = []
    for paper in page_papers:
        authors_str = ", ".join(paper.get("authors", [])[:3])
        if len(paper.get("authors", [])) > 3:
            authors_str += f" +{len(paper['authors']) - 3} more"
        
        df_data.append({
            "标题": paper.get("title", "Untitled"),
            "会议/年份": f"{paper.get('venue', '')} {paper.get('year', '')}",
            "作者": authors_str,
            "平均分": f"{paper.get('avg_score', '-'):.1f}" if paper.get('avg_score') else "-",
            "最高分": f"{paper.get('max_score', '-'):.1f}" if paper.get('max_score') else "-",
            "评审数": paper.get("scored_review_count", 0),
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Expandable details for each paper
    st.markdown("---")
    st.subheader("📄 论文详情")
    
    for i, paper in enumerate(page_papers):
        render_paper_expander(paper, keywords, idx=start_idx + i + 1)


def render_paper_expander(
    paper: Dict[str, Any], 
    keywords: List[str] = None,
    idx: int = 0
) -> None:
    """
    Render expandable paper details.
    """
    title = paper.get("title", "Untitled")
    avg_score = paper.get("avg_score")
    score_str = f"⭐ {avg_score:.1f}" if avg_score else "无评分"
    
    with st.expander(f"**{idx}. {title}** ({score_str})"):
        # Links row
        cols = st.columns([2, 1, 1])
        with cols[0]:
            st.markdown(f"**会议**: {paper.get('venue', '')} {paper.get('year', '')}")
        with cols[1]:
            openreview_url = paper.get("openreview_url", "")
            if openreview_url:
                st.markdown(f"[🔗 OpenReview]({openreview_url})")
        with cols[2]:
            pdf_url = paper.get("pdf_url", "")
            if pdf_url:
                st.markdown(f"[📄 PDF]({pdf_url})")
        
        # Authors
        authors = paper.get("authors", [])
        if authors:
            authors_str = ", ".join(authors)
            st.markdown(f"**作者**: {authors_str}")
        
        # Keywords (from paper metadata)
        paper_keywords = paper.get("keywords", [])
        if paper_keywords:
            st.markdown(f"**关键词**: {', '.join(paper_keywords)}")
        
        # TL;DR
        tldr = paper.get("tldr", "")
        if tldr:
            st.markdown(f"**TL;DR**: {tldr}")
        
        # Abstract with keyword highlighting
        abstract = paper.get("abstract", "")
        if abstract:
            st.markdown("**摘要**:")
            if keywords:
                abstract_html = highlight_keywords(abstract, keywords)
                st.markdown(abstract_html, unsafe_allow_html=True)
            else:
                st.markdown(abstract)
        
        # Score summary
        st.markdown("---")
        st.markdown("**评分统计**")
        score_cols = st.columns(4)
        with score_cols[0]:
            st.metric("平均分", f"{paper.get('avg_score', '-'):.1f}" if paper.get('avg_score') else "-")
        with score_cols[1]:
            st.metric("最高分", f"{paper.get('max_score', '-'):.1f}" if paper.get('max_score') else "-")
        with score_cols[2]:
            st.metric("最低分", f"{paper.get('min_score', '-'):.1f}" if paper.get('min_score') else "-")
        with score_cols[3]:
            st.metric("评审数", paper.get("scored_review_count", 0))
        
        # Individual reviews
        reviews = paper.get("reviews", [])
        if reviews:
            st.markdown("**评审详情**")
            for j, review in enumerate(reviews):
                content = review.get("content", {})
                
                # Extract display info
                review_info = []
                for key in ["rating", "recommendation", "score", "confidence"]:
                    if key in content:
                        val = content[key]
                        if isinstance(val, dict) and "value" in val:
                            val = val["value"]
                        review_info.append(f"{key}: {val}")
                
                if review_info:
                    st.markdown(f"- **Review {j+1}**: {' | '.join(review_info)}")


def export_papers_to_csv(papers: List[Dict[str, Any]]) -> bytes:
    """
    Convert papers to CSV format for download.
    """
    export_data = []
    for paper in papers:
        export_data.append({
            "Title": paper.get("title", ""),
            "Venue": paper.get("venue", ""),
            "Year": paper.get("year", ""),
            "Authors": "; ".join(paper.get("authors", [])),
            "Abstract": paper.get("abstract", ""),
            "Keywords": "; ".join(paper.get("keywords", [])),
            "Avg Score": paper.get("avg_score", ""),
            "Max Score": paper.get("max_score", ""),
            "Min Score": paper.get("min_score", ""),
            "Review Count": paper.get("scored_review_count", 0),
            "Avg Confidence": paper.get("avg_confidence", ""),
            "OpenReview URL": paper.get("openreview_url", ""),
            "PDF URL": paper.get("pdf_url", ""),
        })
    
    df = pd.DataFrame(export_data)
    return df.to_csv(index=False).encode('utf-8')


def render_loading_progress() -> None:
    """
    Create a placeholder for loading progress.
    """
    return st.empty()
