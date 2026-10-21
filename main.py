import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager, nullcontext
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

REQUIREMENTS = {
  "sec1_3": {
    "pdis": (None, "1e-1"),
    "dcgain_db": ("40", None),
    "pm": ("45", None),
    "gbw": ("1e6", None),
    "sr": ("1e5", None),
    "thd": (None, "1.0"),
    "cmrr": ("40", None),
    "psrr": ("40", None),
    "cmir": ("5", None),
    "ovr": ("5", None),
    "area": (None, "1e6"),  # (um^2)
    "ibr": (None, "50"),
  },
  "sec4": {
    "dcgain_db": ("40", None),
    "pm": ("45", None),
    "sr": ("1e6", None),
    "thd": (None, "0.1"),
    "bw": ("2e4", None),
    "ivr": ("0.1", None),
    "vos": (None, "0.1"),
    "area": (None, "2e5"),  # (um^2)
  },
}

ERROR_MESSAGES = {
  10: "入力ネットリストのコピーまたは読み込みに失敗しました。",
  20: "ネットリストの検証・整形に失敗しました。",
  30: "HSPICEが異常終了しました。",
  31: "HSPICE実行ファイルが見つかりません。PATHを確認してください。",
  40: "評価結果の読み取り・算出に失敗しました。",
  50: "シミュレーション用の作業環境の準備に失敗しました。",
}


def read_cc_port(log_path):
  output = log_path.read_text(encoding="utf-8", errors="replace")
  match = re.search(
    r"(?:\bServer\s+is\s+started\s+on\s+|\bport\s*=\s*)(?:[\w.-]+:)?(\d+)\b",
    output, re.IGNORECASE,
  )
  if match and 1 <= int(match[1]) <= 65535:
    return int(match[1])
  return None


@contextmanager
def hspice_cc_port(output_dir):
  """バッチ専用のCCサーバを起動し、終了時に解放する"""
  executable = shutil.which("hspice")
  if executable is None:
    raise RuntimeError("hspiceコマンドがPATH上に見つかりません。")
  log_path = output_dir / "hspice_server.log"
  port = None
  with log_path.open("x", encoding="utf-8") as log:
    try:
      print(f"HSPICE CCサーバを起動してライセンスを取得します。ログ: {log_path}", flush=True)
      # サーバが出力先を継承するため、PIPEではなくファイルへ直接出力する。
      process = subprocess.run(
        [executable, "-CC", "-mp"], cwd=output_dir,
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=120,
      )
      port = read_cc_port(log_path)
      if process.returncode != 0:
        raise RuntimeError(f"CCサーバの起動に失敗しました（終了コード: {process.returncode}）。ログ: {log_path}")
      deadline = time.monotonic() + 5
      while port is None and time.monotonic() < deadline:
        time.sleep(0.1)
        port = read_cc_port(log_path)
      if port is None:
        raise RuntimeError(f"CCポートをログから取得できません。サーバの起動状況を確認してください。ログ: {log_path}")
      print(f"HSPICE CCサーバの準備ができました。ポート: {port}", flush=True)
      yield port
    finally:
      handling_error = sys.exc_info()[0] is not None
      # 起動途中で例外が発生した場合も、取得できたポートは解放する。
      if port is None:
        port = read_cc_port(log_path)
      if port is not None:
        try:
          subprocess.run(
            [executable, "-CC", "-K", "-port", str(port)], cwd=output_dir,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            check=True, timeout=30,
          )
          print(f"HSPICE CCサーバを停止し、ライセンスを解放しました。ポート: {port}", flush=True)
        except (OSError, subprocess.SubprocessError) as error:
          message = f"CCサーバの停止に失敗しました。ポート{port}の解放を確認してください。ログ: {log_path}"
          if not handling_error:
            raise RuntimeError(message) from error
          print(f"{message}\n元のエラー: {error}", file=sys.stderr, flush=True)


def meets_requirements(results, section):
  """評価結果が部門の要求仕様を満たすかどうかを判定"""
  if section not in (1, 2, 3, 4):
    raise ValueError(f"無効な部門です: {section}")
  requirements = REQUIREMENTS["sec4" if section == 4 else "sec1_3"]
  for key, (minimum, maximum) in requirements.items():
    try:
      value = Decimal(str(results[key]))
    except (KeyError, InvalidOperation, ValueError):
      return False
    if (not value.is_finite()
        or (minimum is not None and value < Decimal(minimum))
        or (maximum is not None and value > Decimal(maximum))):
      return False
  return True


def load_module(path):
  """指定されたパスのPythonファイルをモジュールとして読み込む"""
  spec = importlib.util.spec_from_file_location(path.stem, path)
  if spec is None or spec.loader is None:
    raise ImportError(f"Pythonファイルを読み込めません: {path}")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


def evaluate(source, destination, section, port, simset_name="simset"):
  """ネットリストを評価する関数"""
  report = {
    "section": section, "fom": None, "status": "error",
    "error_code": 0, "error": None, "results": {},
  }
  stage = "input"
  try:
    original = destination / source.name
    shutil.copy2(source, original)
    netlist = original.read_text(encoding="utf-8")

    stage = "setup"
    simset_dir = BASE_DIR / simset_name
    check_netlist = load_module(simset_dir / "preprocess.py").check_netlist

    stage = "preprocess"
    processed, voltage, area, *_ = check_netlist(netlist, section)

    stage = "setup"
    spice_dir = destination / "spice"
    spice_dir.mkdir()
    (spice_dir / "opamp.sp").write_text(processed, encoding="utf-8")
    simset = "sec1_3" if section in (1, 2, 3) else "sec4"
    template = simset_dir / simset
    bench = load_module(template / "testbench.py")

    with tempfile.TemporaryDirectory(prefix="netlist_") as temporary:
      work_dir = Path(temporary)
      for deck in template.glob("*.sp"):
        shutil.copy2(deck, work_dir / deck.name)
      (work_dir / "lib").symlink_to(template / "lib", target_is_directory=True)
      (work_dir / "tmp").symlink_to(spice_dir, target_is_directory=True)
      bench.BASE_DIR = str(work_dir)
      bench.TMP_DIR = str(spice_dir)

      stage = "evaluation"
      results = getattr(bench, f"evaluate_{simset}")(port)
    results.update(psvoltage=voltage, area=area)
    json.dumps(results, default=str, allow_nan=False)
    results = {key: str(value) for key, value in results.items()}
    fom = None
    if meets_requirements(results, section):
      fom = results[f"fom{section}" if section in (1, 2, 3) else "fom"]
    else:
      fom = "requirements_not_met"
    report.update(status="success", fom=fom, results=results)
  except Exception as error:
    code = {"input": 10, "preprocess": 20, "setup": 50, "evaluation": 40}[stage]
    if isinstance(error, subprocess.CalledProcessError):
      code = 30
      report["hspice_return_code"] = error.returncode
      for name, data in (("stdout", error.stdout), ("stderr", error.stderr)):
        if data:
          (destination / f"hspice.{name}.log").write_bytes(data)
    elif stage == "evaluation" and isinstance(error, FileNotFoundError) and error.filename == "hspice":
      code = 31
    report.update(error_code=code, error=str(error), error_type=type(error).__name__)
  (destination / "result.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n",
    encoding="utf-8",
  )
  return report


def main():
  parser = argparse.ArgumentParser(description="指定ディレクトリ以下の.spネットリストを一括評価します")
  parser.add_argument("-i", "--input", type=Path, required=True, help="入力ディレクトリ")
  parser.add_argument("-o", "--output", type=Path, required=True, help="出力ディレクトリ")
  parser.add_argument("--sec", type=int, choices=(1, 2, 3, 4), required=True, help="評価する部門")
  parser.add_argument("--cc", action="store_true", help="HSPICE CCサーバを自動起動・解放します")
  parser.add_argument("--simset", default="simset", help="main.pyの配置先を基準とするsimsetのパス（既定: simset）")
  args = parser.parse_args()

  source_dir = args.input.resolve()
  output_dir = args.output.resolve()
  if not source_dir.is_dir():
    parser.error("入力先には存在するディレクトリを指定してください。")
  if output_dir == source_dir or source_dir in output_dir.parents:
    parser.error("出力先は入力ディレクトリの外に指定してください。")

  sources = sorted(
    path for path in source_dir.rglob("*")
    if path.is_file() and not path.is_symlink() and path.suffix.lower() == ".sp"
  )
  if not sources:
    parser.error("入力ディレクトリ以下に.spファイルが見つかりません。")

  destinations = [output_dir / path.relative_to(source_dir) for path in sources]
  if any(path.exists() or path.is_symlink() for path in destinations):
    parser.error("対象ネットリストの出力先が既に存在します。別の出力ディレクトリを指定してください。")

  output_dir.mkdir(parents=True, exist_ok=True)
  with hspice_cc_port(output_dir) if args.cc else nullcontext() as port:
    failed = 0
    for source, destination in zip(sources, destinations):
      destination.mkdir(parents=True)
      report = evaluate(source, destination, args.sec, port, simset_name=args.simset)
      failed += report["status"] != "success"
      if report["status"] == "success":
        print(f"評価完了: {source.relative_to(source_dir)}", flush=True)
      else:
        code = report["error_code"]
        print(f"{ERROR_MESSAGES[code]}（error code: {code}）", file=sys.stderr, flush=True)
        if "hspice_return_code" in report:
          print(f"HSPICEの終了コード: {report['hspice_return_code']}", file=sys.stderr, flush=True)
        print(f"元のエラー: {report['error']}\n結果の保存先: {destination}", file=sys.stderr, flush=True)
  print(f"全{len(sources)}件の処理が終了しました。成功: {len(sources) - failed}件 / 失敗: {failed}件")
  return 1 if failed else 0


if __name__ == "__main__":
  try:
    sys.exit(main())
  except (OSError, RuntimeError, subprocess.SubprocessError) as error:
    print(f"バッチ処理を中止します。\n元のエラー: {error}", file=sys.stderr)
    sys.exit(2)
  except KeyboardInterrupt:
    print("操作によりバッチ処理を中断しました。", file=sys.stderr)
    sys.exit(130)
