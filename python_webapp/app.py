"""
스케줄러 벤치마크 (Level 2 - Goal-based Testing)

아키텍처:
  - 테스트는 "목표/개념"으로 정의 (scheduler-neutral)
  - 각 테스트마다 비교할 스케줄러 명시
  - 공정한 비교만 수행
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from copy import deepcopy

from scheduler.basic_priority import BasicPriorityScheduler
from scheduler.mlfqs import MLFQSScheduler
from scheduler.cfs import CFSScheduler
from workload.generator import generate_workload
from simulator.simulator import Simulator
from analysis.insights import generate_comparison_report
from benchmark.tests import TEST_CATEGORIES, get_test_by_id, ALL_TESTS

# 페이지 설정
st.set_page_config(
    page_title="스케줄러 벤치마크",
    page_icon="⚙️",
    layout="wide"
)

st.markdown(
    """
    <style>
      .cta-link {
        text-decoration: underline;
        text-decoration-thickness: 2px;
        color: inherit;
        transition: color 0.2s ease;
      }
      .cta-link:hover { color: #ff7f50; }
      /* 사이드바 폭 2배로 확장 */
      div[data-testid="stSidebar"] {
        min-width: 42rem;
        max-width: 42rem;
      }
      section[data-testid="stSidebar"] .block-container {
        padding-left: 1.5rem;
        padding-right: 1.5rem;
      }
    </style>
    <div style="font-size:22px; font-weight:700; text-align:center; margin-bottom:12px;">
      👉 <a class="cta-link" href="https://github.com/dvktdr78/scheduler_benchmark?tab=readme-ov-file#%EC%8A%A4%EC%BC%80%EC%A4%84%EB%9F%AC-%EB%B2%A4%EC%B9%98%EB%A7%88%ED%81%AC-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8-%EC%86%8C%EA%B0%90%EB%AC%B8" target="_blank">스케줄러 벤치마크 프로젝트 소감문 보기</a> 👈
    </div>
    """,
    unsafe_allow_html=True,
)

header_col1, header_col2 = st.columns([4, 2])
with header_col1:
    st.title("⚙️ 스케줄러 벤치마크")
with header_col2:
    run_clicked = st.button("🚀 벤치마크 실행", type="primary", use_container_width=True)
    st.markdown(
        "<div style='margin-top:6px; text-align:center; font-weight:600;'>👆 위의 \"벤치마크 실행\" 버튼을 눌러주세요!</div>",
        unsafe_allow_html=True,
    )

st.markdown("""
3가지 CPU 스케줄러를 목표 기반 테스트로 비교 분석합니다.

### 📌 스케줄러 설명

**Nice 값이 뭔가요?**  
- 쉽게 말해 “내가 다른 프로세스들에게 얼마나 양보할까?”를 나타내는 수치입니다. 낮을수록 내가 먼저, 높을수록 남에게 더 양보합니다.  
- Basic/MLFQS는 nice를 `priority` 계산에 넣고, CFS는 `weight`(가중치)로 바꿔 CPU 시간 배분에 씁니다.  
- 범위는 -20(최우선) ~ +19(최하우선), 기본 0이며 값이 높아질수록 CPU를 덜 받고, 낮출수록 더 빨리/많이 받습니다.
- MLFQS에서는 `priority = PRI_MAX - (recent_cpu/4) - 2*nice`로 동적으로 우선순위를 계산해 “최근 CPU 사용량 + nice 의도”를 함께 반영합니다.
- CFS는 Linux 가중치 테이블로 바꿔 vruntime 증가 속도를 조절해, 낮은 nice가 더 긴 CPU 시간을 가져가게 합니다.

**🔵 Basic Priority (정적 우선순위 + RR 4ticks)**  
- 목적: “높은 우선순위 먼저, 나머지는 라운드로빈”.  
- Nice → `priority = 31 - nice`로 한 번만 계산해 고정.  
- 강점: 구현 단순, 오버헤드 최소, 높은 우선순위가 항상 빠름.  
- 약점: 우선순위 낮은 스레드는 오래 기다릴 수 있음(starvation), nice 변경이 실시간 반영되지 않음.

**🟢 MLFQS (64단계 동적 피드백 큐)**  
- 목적: CPU를 많이 쓰는 스레드는 priority를 낮추고, I/O 친화적 스레드는 올려서 응답성을 개선.  
- 매 tick `recent_cpu` 증가, 4 tick마다 priority 재계산, 100 tick마다 `load_avg` 반영.  
- Nice는 priority에 `-2*nice`로 적용 → 영향은 있지만 CFS보다 약함.  
- 강점: I/O bound 우대, starvation 방지, O(1) pick/insert.  
- 약점: 계산 복잡, nice 영향이 상대적으로 약해 비율 테스트에서는 덜 극적.

**🟠 CFS (Linux 스타일 공정성 스케줄러)**  
- 목적: 모든 스레드가 비슷한 `vruntime`을 갖도록 CPU 시간을 가중치 기반으로 나눔.  
- Nice → Linux 가중치 테이블로 변환해 CPU 시간 배분(낮은 nice가 더 긴 시간).  
- 최소 `vruntime`을 가진 스레드를 선택, 실행 시간만큼 `vruntime`을 누적.  
- 강점: 공정성 탁월(Jain Index 높음), nice 효과 강함, starvation 없음.  
- 약점: I/O 우대는 별도 없음, 정렬된 준비큐 관리 비용 존재.
""")

# ========== 설정 UI ==========

st.sidebar.header("⚙️ 테스트 선택")

# 카테고리 선택
category = st.sidebar.selectbox(
    "테스트 카테고리",
    options=list(TEST_CATEGORIES.keys()),
    index=0,
    help="목표/개념별로 테스트가 분류되어 있습니다"
)

# 카테고리 설명
category_info = TEST_CATEGORIES[category]
st.sidebar.info(f"**{category}**\n\n{category_info['description']}")

# 해당 카테고리의 테스트 선택
tests_in_category = category_info['tests']
test_names = [t.name for t in tests_in_category]
test_ids = [t.test_id for t in tests_in_category]

selected_test_name = st.sidebar.selectbox(
    "테스트 선택",
    options=test_names,
    index=0
)

# 선택된 테스트 가져오기
selected_test_idx = test_names.index(selected_test_name)
selected_test = tests_in_category[selected_test_idx]

# 테스트 상세 정보
st.sidebar.markdown("---")
st.sidebar.markdown("### 📋 테스트 정보")
st.sidebar.markdown(f"**목표:** {selected_test.goal}")
st.sidebar.markdown(f"**워크로드:** {selected_test.workload_type}")
st.sidebar.markdown(f"**스레드 수:** {selected_test.thread_count}")
st.sidebar.markdown(f"**비교 대상:** {', '.join(s.upper() for s in selected_test.schedulers)}")
st.sidebar.markdown(f"**주요 메트릭:** {selected_test.primary_metric}")

with st.sidebar.expander("📖 상세 설명"):
    st.markdown(selected_test.description)

# 시뮬레이션 시간
max_ticks = st.sidebar.number_input(
    "시뮬레이션 시간 (ticks)",
    min_value=1000,
    max_value=100000,
    value=35000,
    step=5000,
    help="50개 스레드 완료에 필요한 시간: 약 30,000 ticks"
)

# ========== 실행 버튼 ==========


def fmt_metric(value, fmt=":.1f"):
    """None/숫자 모두 안전하게 포매팅"""
    if value is None:
        return "N/A"
    try:
        return format(value, fmt)
    except Exception:
        return str(value)


def fmt_table_value(key: str, value):
    """테이블 전용 포매터 (공정성 4자리 반올림)"""
    if value is None:
        return "N/A"
    if key == 'fairness':
        try:
            return f"{value:.4f}"
        except Exception:
            return value
    return value

if run_clicked:

    # 실행 시 로딩 영역으로 스크롤 이동
    st.markdown("<div id='result-anchor'></div>", unsafe_allow_html=True)
    components.html(
        """
        <script>
        const el = window.parent.document.getElementById('result-anchor');
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        </script>
        """,
        height=0,
    )

    with st.spinner("🔄 초기화 중..."):
        progress_bar = st.progress(0)
        status_text = st.empty()

    # 워크로드 생성
    with st.spinner(f"📦 워크로드 생성 중... ({selected_test.workload_type}, {selected_test.thread_count} 스레드)"):
        status_text.text(f"워크로드 생성 중... ({selected_test.workload_type}, {selected_test.thread_count} 스레드)")
        base_threads = generate_workload(selected_test.workload_type, selected_test.thread_count, seed=42)
        progress_bar.progress(5)

    # Nice/공정성 극단 테스트는 일부만 완료하도록 시뮬레이션 시간 조정
    actual_max_ticks = max_ticks
    if selected_test.test_id == "nice_effect":
        total_work = sum(t.burst_time for t in base_threads)
        suggested_ticks = int(total_work * 0.2)  # 20%만 실행해도 효과 관찰 가능
        actual_max_ticks = min(max_ticks, suggested_ticks)  # 과도한 런타임 방지
        st.info(
            f"💡 Nice 효과 측정: 시뮬레이션을 최대 {actual_max_ticks:,} ticks까지 실행 "
            f"(입력값 {max_ticks:,} / 총 작업의 20% 기준)"
        )
    elif selected_test.test_id == "fairness_extreme_nice":
        total_work = sum(t.burst_time for t in base_threads)
        suggested_ticks = int(total_work * 0.3)  # 모든 스레드 완료 전에 비율 측정
        actual_max_ticks = min(max_ticks, suggested_ticks)
        st.info(
            f"💡 공정성 극단 Nice: 최대 {actual_max_ticks:,} ticks까지 실행 "
            f"(입력값 {max_ticks:,} / 총 작업의 30% 기준)"
        )

    # 스케줄러 실행
    scheduler_results = {}
    dataframes = {}

    total_schedulers = len(selected_test.schedulers)

    for idx, scheduler_name in enumerate(selected_test.schedulers):
        with st.spinner(f"⚙️ {idx+1}/{total_schedulers}: {scheduler_name.upper()} 시뮬레이션 실행 중..."):
            status_text.text(f"{idx+1}/{total_schedulers}: {scheduler_name.upper()} 시뮬레이션...")

            threads = deepcopy(base_threads)

            # 스케줄러 생성
            if scheduler_name == "basic":
                scheduler = BasicPriorityScheduler(enable_aging=False)
            elif scheduler_name == "mlfqs":
                scheduler = MLFQSScheduler()
            elif scheduler_name == "cfs":
                scheduler = CFSScheduler()
            else:
                st.error(f"Unknown scheduler: {scheduler_name}")
                continue

            # 시뮬레이션 실행
            sim = Simulator(scheduler, threads)
            df = sim.run(max_ticks=actual_max_ticks)

            scheduler_results[scheduler_name] = threads
            dataframes[scheduler_name] = df

            # 진행 상황 업데이트 (5% 워크로드 생성 + 85% 시뮬레이션 + 10% 분석)
            progress_bar.progress(int(5 + (idx + 1) / total_schedulers * 85))

    # Insight 생성
    with st.spinner("📊 결과 분석 중..."):
        status_text.text("분석 중...")
        report = generate_comparison_report(scheduler_results, primary_metric=selected_test.primary_metric)
        progress_bar.progress(95)

    # 세션 저장
    st.session_state['report'] = report
    st.session_state['dataframes'] = dataframes
    st.session_state['test'] = selected_test

    progress_bar.empty()
    status_text.success("✅ 분석 완료!")
    st.markdown("<div id='analysis-anchor'></div>", unsafe_allow_html=True)
    components.html(
        """
        <script>
        const el = window.parent.document.getElementById('analysis-anchor');
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        </script>
        """,
        height=0,
    )


# 결과 표시
if 'report' in st.session_state:
    report = st.session_state['report']
    test = st.session_state['test']
    dataframes = st.session_state['dataframes']

    # 테스트 정보
    st.header(f"📊 테스트: {test.name}")
    st.markdown(f"**목표:** {test.goal}")
    st.markdown(f"**비교 대상:** {', '.join(s.upper() for s in test.schedulers)}")

    # 승자 발표
    st.header(f"🏆 승자: {report['winner'].upper()}")

    # 메트릭 비교 (동적 컬럼 수)
    scheduler_names = test.schedulers
    cols = st.columns(len(scheduler_names))

    # 스케줄러별 색상 매핑
    scheduler_colors = {
        'basic': '🔵',
        'mlfqs': '🟢',
        'cfs': '🟠'
    }

    for col, scheduler_name in zip(cols, scheduler_names):
        with col:
            color = scheduler_colors.get(scheduler_name, '⚪')
            st.subheader(f"{color} {scheduler_name.upper()}")

            metrics = report['metrics'][scheduler_name]

            # 주요 메트릭 강조 표시
            if test.primary_metric == 'avg_wait':
                st.metric("⭐ 평균 대기 시간", f"{fmt_metric(metrics['avg_wait'])} ticks")
                st.metric("평균 반환 시간", f"{fmt_metric(metrics['avg_turnaround'])} ticks")
                st.metric("공정성 지수", f"{fmt_metric(metrics['fairness'], ':.4f')}")
            elif test.primary_metric == 'avg_turnaround':
                st.metric("평균 대기 시간", f"{fmt_metric(metrics['avg_wait'])} ticks")
                st.metric("⭐ 평균 반환 시간", f"{fmt_metric(metrics['avg_turnaround'])} ticks")
                st.metric("공정성 지수", f"{fmt_metric(metrics['fairness'], ':.4f')}")
            elif test.primary_metric == 'fairness':
                st.metric("평균 대기 시간", f"{fmt_metric(metrics['avg_wait'])} ticks")
                st.metric("평균 반환 시간", f"{fmt_metric(metrics['avg_turnaround'])} ticks")
                st.metric("⭐ 공정성 지수", f"{fmt_metric(metrics['fairness'], ':.4f')}")
            elif test.primary_metric == 'cpu_time_ratio':
                st.metric("평균 대기 시간", f"{fmt_metric(metrics['avg_wait'])} ticks")
                st.metric("평균 반환 시간", f"{fmt_metric(metrics['avg_turnaround'])} ticks")
                st.metric("⭐ CPU 시간 비율", f"{fmt_metric(metrics['cpu_time_ratio'], ':.1f')}x")
                st.metric("공정성 지수", f"{fmt_metric(metrics['fairness'], ':.4f')}")
            elif test.primary_metric == 'context_switches':
                st.metric("⭐ 컨텍스트 스위치", f"{metrics['context_switches']}")
                st.metric("평균 대기 시간", f"{fmt_metric(metrics['avg_wait'])} ticks")
                st.metric("평균 반환 시간", f"{fmt_metric(metrics['avg_turnaround'])} ticks")
                st.metric("공정성 지수", f"{fmt_metric(metrics['fairness'], ':.4f')}")
            else:
                st.metric("평균 대기 시간", f"{fmt_metric(metrics['avg_wait'])} ticks")
                st.metric("평균 반환 시간", f"{fmt_metric(metrics['avg_turnaround'])} ticks")
                st.metric("공정성 지수", f"{fmt_metric(metrics['fairness'], ':.4f')}")

            if metrics.get('has_starvation'):
                st.warning("⚠️ Starvation 위험")

    # 개선율 표시 (baseline이 있는 경우)
    if len(report['improvements']) > 0:
        st.subheader(f"📈 {report['baseline'].upper()} 대비 개선율")

        improvement_cols = st.columns(len(report['improvements']))
        for col, (key, value) in zip(improvement_cols, report['improvements'].items()):
            scheduler_name = key.split('_vs_')[0]
            with col:
                st.metric(f"{scheduler_name.upper()}", f"{value:+.1f}%")

    # 핵심 Insight
    st.header("💡 핵심 발견사항")
    for insight in report['insights']:
        st.info(insight)

    # 비교 차트
    st.header("📊 성능 비교")

    # 메트릭 비교 테이블
    metrics_rows = [
        ('평균 대기 시간', 'avg_wait'),
        ('평균 반환 시간', 'avg_turnaround'),
        ('공정성', 'fairness'),
    ]
    if test.primary_metric == 'cpu_time_ratio':
        metrics_rows.append(('CPU 시간 비율', 'cpu_time_ratio'))
    if test.primary_metric == 'context_switches':
        metrics_rows.append(('컨텍스트 스위치', 'context_switches'))

    metrics_data = {'Metric': [label for label, _ in metrics_rows]}

    for scheduler_name in scheduler_names:
        metrics = report['metrics'][scheduler_name]
        metrics_data[scheduler_name.upper()] = [
            fmt_table_value(key, metrics[key]) for _, key in metrics_rows
        ]

    comparison_df = pd.DataFrame(metrics_data)
    st.dataframe(comparison_df, use_container_width=True)

    # 개선율 그래프 (baseline이 있는 경우)
    if len(report['improvements']) > 0:
        st.subheader(f"📈 {report['baseline'].upper()} 대비 개선율")

        improvement_data = []
        for key, value in report['improvements'].items():
            scheduler_name = key.split('_vs_')[0]
            improvement_data.append({
                'Scheduler': scheduler_name.upper(),
                'Improvement': value
            })

        if improvement_data:
            schedulers = [d['Scheduler'] for d in improvement_data]
            values = [d['Improvement'] for d in improvement_data]
            colors = ['green' if v > 0 else 'red' for v in values]

            fig = go.Figure()
            fig.add_bar(
                y=schedulers,
                x=values,
                orientation='h',
                marker_color=colors,
                text=[f"{v:+.1f}%" for v in values],
                textposition='outside'
            )

            # 얇은 차트로 가독성 개선, 중앙 0선 표시
            fig.update_layout(
                height=max(160, 80 + 40 * len(values)),
                xaxis_title="개선율 (%)",
                yaxis_title="",
                xaxis=dict(zeroline=True, zerolinecolor='gray', zerolinewidth=1),
                margin=dict(l=80, r=40, t=20, b=40)
            )

            st.plotly_chart(fig, use_container_width=True)

    # 상세 데이터
    st.header("📋 상세 데이터")

    tabs = st.tabs([s.upper() for s in scheduler_names])

    for tab, scheduler_name in zip(tabs, scheduler_names):
        with tab:
            st.dataframe(dataframes[scheduler_name].head(100))

else:
    # 초기 화면
    st.info("👆 위의 '벤치마크 실행' 버튼을 눌러주세요!")

    st.markdown("""
    ### 🎯 테스트 카테고리

    1. **일반 워크로드** (3-way)
       - Mixed, CPU-bound, I/O-bound
       - 모든 스케줄러 비교

    2. **실제 응용** (3-way)
       - 웹 서버, 데이터베이스, 배치, 게임
       - 실제 시스템 패턴

    3. **공정성** (MLFQS vs CFS)
       - Starvation 방지
       - 공정한 CPU 배분

    4. **Nice 효과** (MLFQS vs CFS)
       - Nice 값의 실제 효과
       - 스케줄러별 해석 방식

    5. **확장성** (3-way)
       - 10, 100, 500 스레드
       - 스케일링 능력
    """)

st.markdown("---")
