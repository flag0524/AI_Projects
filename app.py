import gradio as gr
from tryon_engine import TryOnEngine
import os

# 엔진 초기화
engine = TryOnEngine()

def process_tryon(mannequin_img, top_img, bottom_img, mode):
    if mannequin_img is None:
        return None
    
    # 임시 파일 경로 설정
    m_path = "temp_mannequin.png"
    t_path = "temp_top.png"
    b_path = "temp_bottom.png"
    
    # PIL 이미지를 파일로 저장
    mannequin_img.save(m_path)
    
    top_path = None
    if top_img is not None:
        top_img.save(t_path)
        top_path = t_path
        
    bottom_path = None
    if bottom_img is not None:
        bottom_img.save(b_path)
        bottom_path = b_path

    if mode == "상의만":
        bottom_path = None
    elif mode == "하의만":
        top_path = None

    try:
        result = engine.fit_clothing_hybrid(m_path, top_path, bottom_path)
        return result
    except Exception as e:
        print(f"Error during fitting: {e}")
        return None

with gr.Blocks(title="Blandu AI Try-On") as demo:
    gr.Markdown("# 👕 마네킹 AI 가상 피팅 시스템")
    gr.Markdown("마네킹 이미지와 의류 이미지를 업로드하여 피팅 결과를 확인하세요.")
    
    with gr.Row():
        with gr.Column():
            mannequin_input = gr.Image(label="마네킹 이미지 (Base)", type="pil")
            top_input = gr.Image(label="상의 이미지 (Top)", type="pil")
            bottom_input = gr.Image(label="하의 이미지 (Bottom)", type="pil")
            mode_input = gr.Radio(["전체 피팅", "상의만", "하의만"], label="피팅 모드", value="전체 피팅")
            submit_btn = gr.Button("피팅 시작 ✨", variant="primary")
        
        with gr.Column():
            output_image = gr.Image(label="최종 피팅 결과")

    submit_btn.click(
        fn=process_tryon,
        inputs=[mannequin_input, top_input, bottom_input, mode_input],
        outputs=output_image
    )

if __name__ == "__main__":
    # 포트 번호를 명시하지 않음 -> Gradio가 자동으로 빈 포트 할당
    demo.launch(server_name="0.0.0.0")