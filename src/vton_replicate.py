"""
IDM-VTON 기반 가상 피팅 (Replicate API)
- cuuupid/idm-vton 모델 사용
- 마네킹 + 상의 → 중간결과 → 중간결과 + 하의 → 최종 결과
"""
import os
import io
import base64
from pathlib import Path
from PIL import Image


def encode_image_b64(path: Path) -> str:
    """이미지를 base64 data URI로 인코딩"""
    ext = path.suffix.lstrip(".").lower()
    if ext == "jpg":
        ext = "jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/{ext};base64,{b64}"


def save_url_image(url: str, out_path: Path):
    """URL에서 이미지 다운로드 후 저장"""
    import urllib.request
    urllib.request.urlretrieve(url, str(out_path))
    print(f"  저장: {out_path.name}")


def run_vton():
    import replicate

    # ── 경로 ──────────────────────────────────────────────
    raw       = Path(r"d:\blandu_project\input\raw_photos")
    out_dir   = Path(r"d:\blandu_project\output\hybrid")
    out_dir.mkdir(parents=True, exist_ok=True)

    mannequin = raw / "마네킹.jpg"
    top_img   = raw / "ITEM-001.png"
    bottom_img= raw / "ITEM-002.png"
    mid_out   = out_dir / "VTON_STEP1_TOP.png"
    final_out = out_dir / "VTON_FINAL_TOTAL_LOOK.png"

    # ── Step 1: 마네킹 + 상의 ─────────────────────────────
    print("[1/2] IDM-VTON: 마네킹에 상의 착장 중...")
    output1 = replicate.run(
        "cuuupid/idm-vton",
        input={
            "human_img":    encode_image_b64(mannequin),
            "garm_img":     encode_image_b64(top_img),
            "garment_des":  "white long-sleeve belted shirt blouse with collar, front pocket, and peplum hem",
            "is_checked":       True,
            "is_checked_crop":  False,
            "denoise_steps":    30,
            "seed":             42,
            "category":         "upper_body",
        }
    )

    # output1은 URL 리스트 또는 FileOutput 객체
    if isinstance(output1, list):
        result_url1 = str(output1[0])
    else:
        result_url1 = str(output1)

    save_url_image(result_url1, mid_out)
    print(f"  Step1 완료: {mid_out.name}")

    # ── Step 2: Step1 결과 + 하의 ─────────────────────────
    print("[2/2] IDM-VTON: 하의 착장 중...")
    output2 = replicate.run(
        "cuuupid/idm-vton",
        input={
            "human_img":    encode_image_b64(mid_out),
            "garm_img":     encode_image_b64(bottom_img),
            "garment_des":  "light grey ice-blue wide leg straight denim pants",
            "is_checked":       True,
            "is_checked_crop":  False,
            "denoise_steps":    30,
            "seed":             42,
            "category":         "lower_body",
        }
    )

    if isinstance(output2, list):
        result_url2 = str(output2[0])
    else:
        result_url2 = str(output2)

    save_url_image(result_url2, final_out)
    print(f"\n[DONE] 최종 결과: {final_out}")


if __name__ == "__main__":
    token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not token:
        print("=" * 60)
        print("❌ REPLICATE_API_TOKEN 이 설정되지 않았습니다.")
        print()
        print("아래 단계를 따라 API 토큰을 설정해 주세요:")
        print()
        print("1. https://replicate.com 에 가입/로그인")
        print("2. https://replicate.com/account/api-tokens 에서 토큰 생성")
        print("3. 아래 명령어로 토큰 설정:")
        print()
        print('   $env:REPLICATE_API_TOKEN="r8_xxxx..."   # PowerShell')
        print('   set REPLICATE_API_TOKEN=r8_xxxx...      # CMD')
        print()
        print("4. 다시 실행:")
        print("   python -m src.vton_replicate")
        print("=" * 60)
    else:
        run_vton()
