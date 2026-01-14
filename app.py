"""
OpenReview Paper Filtering & Scoring Analysis Tool
Main Streamlit Application

A web app for filtering and analyzing papers from OpenReview
by conference, year, keywords, and review scores.
"""

import streamlit as st
from typing import List, Dict, Any
import importlib

# Force reload modules to handle hot-reloading issues
import config
import ui_components
import openreview_client
import parsing
importlib.reload(config)
importlib.reload(ui_components)
importlib.reload(openreview_client)
importlib.reload(parsing)

from parsing import (
    filter_paper_by_keywords,
    sort_papers,
)
from ui_components import (
    render_sidebar_filters,
    render_filter_summary,
    render_paper_table,
    export_papers_to_csv,
)


# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="OpenReview 论文筛选工具",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    mark {
        background-color: #ffeb3b !important;
        padding: 0 2px;
    }
    .stDataFrame {
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def init_session_state():
    """Initialize session state variables."""
    if "papers" not in st.session_state:
        st.session_state.papers = []
    if "filtered_papers" not in st.session_state:
        st.session_state.filtered_papers = []
    if "current_page" not in st.session_state:
        st.session_state.current_page = 0
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False
    if "load_status" not in st.session_state:
        st.session_state.load_status = ""
    if "last_filters" not in st.session_state:
        st.session_state.last_filters = {}


init_session_state()


# ============================================================================
# DATA LOADING
# ============================================================================

def load_data(filters: Dict[str, Any]) -> None:
    """
    Load papers based on filter settings.
    Uses staged progress display for better user feedback.
    """
    # Determine what to load
    venues_to_load = []
    
    if filters["custom_venue"]:
        venues_to_load.append(("custom", filters["custom_venue"]))
    else:
        for venue in filters["venues"]:
            for year in range(filters["year_start"], filters["year_end"] + 1):
                venues_to_load.append((venue, year))
    
    if not venues_to_load:
        st.warning("请选择至少一个会议或输入自定义 Venue ID")
        return
    
    all_papers = []
    status_messages = []
    total_tasks = len(venues_to_load)
    
    # Import needed modules
    from openreview_client import fetch_submissions_with_reviews
    from config import get_venue_id_candidates as get_candidates
    
    # Use st.status for staged progress display
    with st.status("📡 正在加载数据（包含评审，约需 2-3 分钟）...", expanded=True) as status:
        
        for task_idx, item in enumerate(venues_to_load):
            if item[0] == "custom":
                venue_display = item[1]
                venue_id = item[1]
                year = filters["year_start"]
            else:
                venue, year = item
                venue_display = f"{venue} {year}"
                venue_id = None
            
            # Stage 1
            st.write(f"🔗 **[{task_idx + 1}/{total_tasks}] {venue_display}**")
            
            # Get venue ID candidates
            if venue_id:
                venue_ids = [venue_id]
            else:
                venue_ids = get_candidates(venue, year)
            
            papers = []
            success = False
            
            for vid in venue_ids:
                # Fetch submissions WITH reviews
                st.write(f"📄 获取论文和评审数据（请耐心等待）...")
                fetched_papers, fetch_status = fetch_submissions_with_reviews(vid)
                
                if fetched_papers:
                    # Add year/venue info
                    for paper in fetched_papers:
                        paper["year"] = year
                        paper["venue"] = venue if not venue_id else venue_id
                    
                    papers = fetched_papers
                    
                    reviewed_count = sum(1 for p in papers if p.get("scored_review_count", 0) > 0)
                    st.write(f"✅ 找到 **{len(papers)}** 篇论文（{reviewed_count} 篇有评审）")
                    status_msg = f"{venue_display}: {len(papers)} 篇论文 ({reviewed_count} 有评审)"
                    status_messages.append(status_msg)
                    success = True
                    break
            
            if not success:
                st.write(f"⚠️ **{venue_display}** - 未找到数据")
                status_messages.append(f"{venue_display}: 未找到数据")
            
            all_papers.extend(papers)
        
        # Final status
        if all_papers:
            reviewed_total = sum(1 for p in all_papers if p.get("scored_review_count", 0) > 0)
            status.update(
                label=f"✅ 加载完成！{len(all_papers)} 篇论文（{reviewed_total} 篇有评审）",
                state="complete",
                expanded=False
            )
        else:
            status.update(label="❌ 未能加载任何论文", state="error")
    
    # Update session state
    st.session_state.papers = all_papers
    st.session_state.data_loaded = True
    st.session_state.load_status = "\n".join(status_messages)
    st.session_state.current_page = 0


def apply_filters(papers: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply keyword and score filters to papers.
    """
    from parsing import filter_paper_by_scores
    
    filtered = []
    
    for paper in papers:
        # Only reviewed filter
        if filters.get("only_reviewed", False):
            if paper.get("scored_review_count", 0) == 0:
                continue
        
        # Keyword filter
        if not filter_paper_by_keywords(
            paper,
            filters["keywords"],
            filters["field_scope"],
            filters["keyword_logic"]
        ):
            continue
        
        # Score filters
        if not filter_paper_by_scores(
            paper,
            min_avg_score=filters.get("min_avg_score"),
            min_max_score=filters.get("min_max_score"),
            min_review_count=filters.get("min_review_count"),
            min_confidence=filters.get("min_confidence"),
        ):
            continue
        
        filtered.append(paper)
    
    # Sort
    sorted_papers = sort_papers(filtered, filters["sort_by"], ascending=False)
    
    return sorted_papers


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point."""
    
    # Header
    st.markdown('<p class="main-header">📚 OpenReview 论文筛选与评分分析</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">按会议、年份、关键词、评分筛选 OpenReview 论文，查看评审详情</p>',
        unsafe_allow_html=True
    )
    
    # Calculate dataset statistics for adaptive UI
    max_score_in_dataset = 10.0  # Default assumption
    if st.session_state.papers:
        # Find the absolute maximum score in the loaded dataset
        # Filter out None values
        valid_max_scores = [
            p.get("max_score") 
            for p in st.session_state.papers 
            if p.get("max_score") is not None
        ]
        
        if valid_max_scores:
            max_score_in_dataset = max(valid_max_scores)
            
            # If explicit refresh, update session state cache
            if 'max_score_dataset' not in st.session_state or st.session_state.get('data_loaded', False):
                st.session_state.max_score_dataset = max_score_in_dataset
    
    # Use cached value if available
    if 'max_score_dataset' in st.session_state:
        max_score_in_dataset = st.session_state.max_score_dataset

    # Sidebar filters
    filters = render_sidebar_filters(max_score_in_dataset=max_score_in_dataset)
    
    # Load data button in sidebar
    st.sidebar.markdown("---")
    load_clicked = st.sidebar.button(
        "🔄 加载数据",
        type="primary",
        use_container_width=True,
        help="点击加载选定会议和年份的论文数据"
    )
    
    if load_clicked:
        load_data(filters)
    
    # Clear cache button
    if st.sidebar.button("🗑️ 清除缓存", use_container_width=True):
        st.cache_data.clear()
        st.session_state.papers = []
        st.session_state.filtered_papers = []
        st.session_state.data_loaded = False
        st.success("缓存已清除")
        st.rerun()
    
    # Main content area
    st.markdown("---")
    
    if not st.session_state.data_loaded:
        st.info("👈 请在左侧选择会议和年份，然后点击「加载数据」按钮")
        
        # Show usage instructions
        with st.expander("📖 使用说明", expanded=True):
            st.markdown("""
            ### 快速开始
            1. **选择会议**: 在左侧边栏选择一个或多个会议（如 ICLR, NeurIPS）
            2. **选择年份**: 调整年份范围滑块
            3. **加载数据**: 点击「加载数据」按钮
            4. **筛选与浏览**: 使用关键词和评分筛选功能找到感兴趣的论文
            
            ### 支持的会议
            - **ICLR**: 2018-2026
            - **NeurIPS**: 2019-2026 (别名: nips)
            - **ICML**: 2023-2026
            - **AAAI**: 2023-2026
            - **AAMAS**: 2023-2026
            
            ### 自定义 Venue
            如果你知道 OpenReview 的 Venue ID，可以直接在「自定义 Venue ID」输入框中输入。
            例如: `ICLR.cc/2024/Conference`
            
            ### 评分说明
            - **avg_score**: 所有评审分数的平均值
            - **max_score**: 所有评审分数的最高值
            - **review_count**: 有效评分的评审数量
            """)
        return
    
    # Apply filters to loaded papers
    filtered_papers = apply_filters(st.session_state.papers, filters)
    st.session_state.filtered_papers = filtered_papers
    
    # Filter summary
    render_filter_summary(filters, len(filtered_papers), len(st.session_state.papers))
    
    # Export button
    col1, col2 = st.columns([3, 1])
    with col2:
        if filtered_papers:
            csv_data = export_papers_to_csv(filtered_papers)
            st.download_button(
                label="📥 导出 CSV",
                data=csv_data,
                file_name="openreview_papers.csv",
                mime="text/csv",
                use_container_width=True,
            )
    
    # Paper table
    render_paper_table(
        filtered_papers,
        st.session_state.current_page,
        filters["page_size"],
        keywords=filters["keywords"],
    )


if __name__ == "__main__":
    main()
