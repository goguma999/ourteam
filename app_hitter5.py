import os
import tempfile
import streamlit as st
import cv2
from moviepy.editor import VideoFileClip, vfx
from ultralytics import YOLO
from collections import defaultdict
import urllib.request

# 전체 레이아웃을 넓게 설정
st.set_page_config(layout="wide")

# 제목
st.title("⚾ Who is the batter ⚾")

# GitHub에 업로드된 모델 경로
MODEL_URL = "https://github.com/yourusername/yourrepository/raw/main/6_trained_model.pt"
model_path = "6_trained_model.pt"

# 모델 파일이 없을 경우 다운로드
if not os.path.exists(model_path):
    st.info("모델 파일을 다운로드 중입니다...")
    urllib.request.urlretrieve(MODEL_URL, model_path)
    st.success("모델 다운로드 완료!")

# YOLO 모델 로드
model = YOLO(model_path)

# 비디오 파일 업로드
uploaded_file = st.file_uploader("비디오 파일을 업로드하세요", type=["mp4", "mov", "avi"])

# 속도 선택 슬라이더 추가
speed = st.slider("재생 속도 선택", 0.25, 1.0, 1.0, step=0.25)

# 전체 레이아웃을 컨테이너로 감싸기
with st.container():
    col1, col2 = st.columns(2)

    with col1:
        st.header("원본 영상")
        if uploaded_file is not None:
            st.video(uploaded_file)
        else:
            st.markdown(
                """
                <div style='width:100%; height:300px; background-color:#d3d3d3; display:flex; align-items:center; justify-content:center; border-radius:5px;'>
                    <p style='color:#888;'>원본 영상이 여기에 표시됩니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col2:
        st.header("타자 분석 결과 영상")
        result_placeholder = st.empty()
        if "processed_video" in st.session_state and st.session_state["processed_video"] is not None:
            result_placeholder.video(st.session_state["processed_video"])
        else:
            result_placeholder.markdown(
                """
                <div style='width:100%; height:300px; background-color:#d3d3d3; display:flex; align-items:center; justify-content:center; border-radius:5px;'>
                    <p style='color:#888;'>여기에 타자 분석 결과가 표시됩니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

# 페이지 하단에 결과 정보 미리 표시
st.write("### 결과 정보")
most_frequent_class_placeholder = st.empty()
frequent_detection_placeholder = st.empty()

most_frequent_class_placeholder.write("1) 영상 속 타자는 **_______** 입니다.")
frequent_detection_placeholder.write("2) 가장 먼저 50프레임 도달한 인물: **_______**")

# 사물 검출 실행 버튼
if st.button("타자 분석 실행") and uploaded_file:
    # 임시 파일 경로 생성
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_output:
        output_path = temp_output.name

    # 원본 비디오 파일을 임시 파일로 저장
    with tempfile.NamedTemporaryFile(delete=False) as temp_input:
        temp_input.write(uploaded_file.read())
        temp_input_path = temp_input.name

    # 비디오 처리 시작
    cap = cv2.VideoCapture(temp_input_path)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # 검출된 인물 횟수를 추적하는 변수들
    detection_counts = defaultdict(int)
    frequent_detection = None
    confidence_threshold = 0.65

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # YOLO 모델로 예측 수행
        results = model(frame)
        detections = results[0].boxes if len(results) > 0 else []

        # 검출된 객체에 대해 바운딩 박스 그리기
        for box in detections:
            if box.conf[0] >= confidence_threshold:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                confidence = box.conf[0]
                class_id = int(box.cls[0])
                class_name = model.names[class_id]
                
                # 검출 횟수 증가 및 50프레임 도달 확인
                detection_counts[class_name] += 1
                if detection_counts[class_name] >= 50 and frequent_detection is None:
                    frequent_detection = class_name

                label = f"{class_name} {confidence:.2f}"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        out.write(frame)

    cap.release()
    out.release()

    # 가장 많이 검출된 인물
    most_frequent_class = max(detection_counts, key=detection_counts.get, default="None")

    # moviepy를 사용해 재인코딩 및 속도 조정
    reencoded_path = output_path.replace(".mp4", f"_speed_{speed}x.mp4")
    clip = VideoFileClip(output_path).fx(vfx.speedx, speed)
    clip.write_videofile(reencoded_path, codec="libx264", audio_codec="aac")

    # 재인코딩된 비디오 경로를 세션에 저장하고 col2에 표시
    st.session_state["processed_video"] = reencoded_path
    result_placeholder.video(st.session_state["processed_video"])

    # 재인코딩된 비디오 다운로드 버튼 제공
    with open(reencoded_path, "rb") as file:
        st.download_button(
            label="재인코딩된 결과 영상 다운로드",
            data=file,
            file_name=f"reencoded_video_{speed}x.mp4",
            mime="video/mp4"
        )

    # 페이지 하단에 가장 많이 검출된 인물과 50프레임 도달한 인물 표시
    most_frequent_class_placeholder.write(f"1) 영상 속 타자는 **{most_frequent_class}** 입니다.")
    if frequent_detection:
        frequent_detection_placeholder.write(f"2) 가장 먼저 50프레임 도달한 인물: **{frequent_detection}**")
    else:
        frequent_detection_placeholder.write("2) 가장 먼저 50프레임 도달한 인물: **없음**")