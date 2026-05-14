"""
main.py — BMS (BLANCDEW Mannequin Styler) 메인 CLI
typer 기반 커맨드라인 인터페이스입니다.

사용법:
    python src/main.py run --item BLD-2401 --preset single_front
    python src/main.py run --codi C001 --preset codi_full
    python src/main.py run --all --preset single_front
    python src/main.py presets
    python src/main.py report
    python src/main.py validate
    python src/main.py excel-sample
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# src 폴더를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

import typer
from loguru import logger
from tqdm import tqdm

from config import (
    PRESETS_FILE, LOG_FILE, LOGS_DIR,
    RAW_PHOTOS_DIR, CODI_SETS_DIR, OUTPUT_DIR,
)
from excel_reader import load_product_data, validate_mapping
from codi_mapper import load_codi_sets, resolve_codi_images
from composer import compose_single, compose_codi
from layout_engine import save_single, build_lookbook_2col, build_catalog_card

app = typer.Typer(
    name="bms",
    help="🧥 BLANCDEW Mannequin Styler — 마네킹 착장 이미지 생성기",
    add_completion=False,
)

# ─────────────────────────────────────────────
# 로그 설정
# ─────────────────────────────────────────────
def _setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    logger.add(
        str(LOG_FILE),
        level="DEBUG",
        rotation="10 MB",
        encoding="utf-8",
        serialize=True,  # JSONL 형식
    )


def _load_presets() -> dict:
    with open(PRESETS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return {p["id"]: p for p in data["presets"]}


# ─────────────────────────────────────────────
# CLI 명령어
# ─────────────────────────────────────────────

@app.command()
def run(
    item:   str  = typer.Option(None,  "--item",   "-i", help="단일 품번 (예: BLD-2401)"),
    codi:   str  = typer.Option(None,  "--codi",   "-c", help="코디 번호 (예: C001)"),
    all_:   bool = typer.Option(False, "--all",    "-a", help="raw_photos 전체 처리"),
    preset: str  = typer.Option("single_front", "--preset", "-p", help="연출 프리셋 ID"),
):
    """상품 이미지를 마네킹 착장 이미지로 변환합니다."""
    _setup_logging()
    presets  = _load_presets()
    products = load_product_data()
    codi_map = load_codi_sets()

    if preset not in presets:
        typer.echo(f"❌ 프리셋 '{preset}' 없음. 'python src/main.py presets' 로 목록 확인")
        raise typer.Exit(1)

    p = presets[preset]
    results = {"ok": 0, "skip": 0, "error": 0}

    # ── 단일 품번 처리 ──
    if item:
        _process_item(item, p, products, results)

    # ── 코디 세트 처리 ──
    elif codi:
        _process_codi(codi, p, products, codi_map, results)

    # ── 전체 일괄 처리 ──
    elif all_:
        all_items = [f.stem for f in RAW_PHOTOS_DIR.glob("*.jpg")]
        all_items += [f.stem for f in RAW_PHOTOS_DIR.glob("*.png")]
        logger.info(f"전체 처리 시작: {len(all_items)}개 이미지")

        for item_code in tqdm(all_items, desc="처리 중"):
            _process_item(item_code, p, products, results)

    else:
        typer.echo("❌ --item / --codi / --all 중 하나를 지정하세요.")
        raise typer.Exit(1)

    # ── 결과 요약 ──
    typer.echo(f"\n✅ 완료: {results['ok']}개 | ⚠️ 건너뜀: {results['skip']}개 | ❌ 오류: {results['error']}개")


@app.command()
def presets():
    """사용 가능한 연출 프리셋 목록을 출력합니다."""
    _setup_logging()
    data = _load_presets()
    typer.echo("\n🎨 사용 가능한 연출 프리셋:\n")
    for pid, p in data.items():
        size = p.get("output_size", ["-", "-"])
        typer.echo(f"  {pid:<20} {p['name']:<15} {size[0]}×{size[1]}  — {p['description']}")
    typer.echo()


@app.command()
def validate():
    """엑셀 품번 ↔ 이미지 파일 매핑 검증 리포트를 출력합니다."""
    _setup_logging()
    products = load_product_data()
    result   = validate_mapping(products, RAW_PHOTOS_DIR)

    typer.echo(f"\n📋 매핑 검증 결과:")
    typer.echo(f"  ✅ 매칭:        {len(result['matched'])}개")
    typer.echo(f"  ⚠️  엑셀 전용:   {len(result['excel_only'])}개 (이미지 없음)")
    typer.echo(f"  ⚠️  파일 전용:   {len(result['file_only'])}개 (엑셀 등록 필요)")

    if result["excel_only"]:
        typer.echo(f"\n  이미지 없는 품번: {result['excel_only']}")
    if result["file_only"]:
        typer.echo(f"\n  엑셀 미등록 파일: {result['file_only']}")


@app.command()
def report():
    """처리 로그 요약 리포트를 출력합니다."""
    _setup_logging()
    if not LOG_FILE.exists():
        typer.echo("로그 파일이 없습니다. 먼저 'run' 명령을 실행하세요.")
        return

    ok = skip = error = 0
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                rec = entry.get("record", {})
                extra = rec.get("extra", {})
                status = extra.get("status", "")
                if status == "ok":     ok += 1
                elif status == "skip": skip += 1
                elif status == "error": error += 1
            except json.JSONDecodeError:
                continue

    typer.echo(f"\n📊 처리 로그 요약:")
    typer.echo(f"  ✅ 성공: {ok}개")
    typer.echo(f"  ⚠️  건너뜀: {skip}개")
    typer.echo(f"  ❌ 오류: {error}개")


@app.command(name="excel-sample")
def excel_sample():
    """샘플 product_data.xlsx를 생성합니다."""
    _setup_logging()
    from create_sample_excel import create_sample_excel
    create_sample_excel()


# ─────────────────────────────────────────────
# 내부 처리 함수
# ─────────────────────────────────────────────

def _process_item(item_code: str, preset: dict, products: dict, results: dict):
    """단일 품번 처리"""
    if item_code not in products:
        logger.warning(f"{item_code}: 엑셀에 없음 → 건너뜀", status="skip")
        results["skip"] += 1
        return

    # 이미지 파일 탐색
    img_path = _find_raw_image(item_code)
    if img_path is None:
        logger.warning(f"{item_code}: 이미지 파일 없음 → 건너뜀", status="skip")
        results["skip"] += 1
        return

    product = products[item_code]

    try:
        image = compose_single(
            item_code     = item_code,
            image_path    = img_path,
            category      = product.get("category", "상의"),
            mannequin_view= preset.get("mannequin", "front"),
            background_name= preset.get("background", "bg_white"),
            output_size   = tuple(preset.get("output_size", [800, 1200])),
        )

        if image is None:
            results["error"] += 1
            return

        # 워터마크 (카탈로그 프리셋)
        if preset.get("watermark"):
            image = build_catalog_card(
                image     = image,
                item_code = item_code,
                item_name = product.get("item_name", ""),
                price     = product.get("price", 0),
                output_size= tuple(preset.get("output_size", [800, 1100])),
            )

        out_path = save_single(image, item_code, preset["id"], preset.get("output_folder", "single"))
        logger.info(f"{item_code} → {out_path.name}", status="ok")
        results["ok"] += 1

    except Exception as e:
        logger.error(f"{item_code}: 처리 중 오류 — {e}", status="error")
        results["error"] += 1


def _process_codi(codi_id: str, preset: dict, products: dict, codi_map: dict, results: dict):
    """코디 세트 처리"""
    items = resolve_codi_images(codi_id, codi_map, products)
    if not items:
        logger.warning(f"코디 {codi_id}: 처리 가능한 아이템 없음")
        results["skip"] += 1
        return

    try:
        image = compose_codi(
            codi_items     = items,
            mannequin_view = preset.get("mannequin", "front"),
            background_name= preset.get("background", "bg_studio"),
            output_size    = tuple(preset.get("output_size", [800, 1200])),
        )

        if image is None:
            results["error"] += 1
            return

        out_path = save_single(image, codi_id, preset["id"], preset.get("output_folder", "codi"))
        logger.info(f"코디 {codi_id} → {out_path.name}", status="ok")
        results["ok"] += 1

    except Exception as e:
        logger.error(f"코디 {codi_id}: 처리 중 오류 — {e}", status="error")
        results["error"] += 1


def _find_raw_image(item_code: str) -> Path | None:
    for ext in [".jpg", ".jpeg", ".png"]:
        p = RAW_PHOTOS_DIR / f"{item_code}{ext}"
        if p.exists():
            return p
    return None


if __name__ == "__main__":
    app()
