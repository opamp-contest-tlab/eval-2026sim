import os, re, subprocess
import pandas as pd
from decimal import Decimal

# このスクリプトが置かれているディレクトリのパス
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# tmpディレクトリのパス
TMP_DIR = os.path.join(BASE_DIR, 'tmp')

def main():
  """
  動作確認用関数
  """
  results = evaluate_sec4()

  for key, value in results.items():
    print(f"{key}: {value:.3e}")

def evaluate_sec4(port=None):
  """
  一連のシミュレーションを実行する関数
  """
  # 結果を格納する辞書
  results = {}

  # シミュレーション実行
  return_code = _run_hspice(os.path.join(BASE_DIR, 'sim.sp'), os.path.join(TMP_DIR, 'result.lis'), port)
  if return_code != 0:
    # エラーを吐いて終了
    raise RuntimeError(f"HSPICE first time simulation failed with return code {return_code}")

  """直流利得/位相余裕"""
  results['dcgain_db'], results['pm'] = _get_ac1()

  """帯域幅"""
  results['bw'] = _get_bw()

  """消費電流/消費電力/オフセット電圧"""
  results['ib'], results['pdis'], results['vos'] = _get_dc()

  """スルーレート"""
  results['sr'] = _get_sr()

  """全高調波歪"""
  results['thd'] = _get_thd()

  """入力電圧範囲"""
  results['ivr'] = _get_ivr()

  """スコアの算出"""
  results['fom'] = Decimal('1.0') / results['pdis']


  return results

  
def _run_hspice(input_file, output_file, port=None):
  """
  HSPICEを実行する関数
  """
  if port is not None:
    # Advanced Server/ClientモードでHSPICE実行
    command = ['hspice', '-CC', '-i', input_file, '-o', output_file, '-port', str(port)]
  else:
    # Anonymous LicenceモードでHSPICE実行
    command = ['hspice', '-i', input_file, '-o', output_file]

  # HSPICE実行
  result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=BASE_DIR)
  result.check_returncode()

  # 終了コードを返す
  return result.returncode

def _read_csv(file_path):
  """
  HSPICEが出力するCSVファイルを読み込む関数

  ヘッダの3行を読み飛ばす
  """
  return pd.read_csv(file_path, skiprows=3, dtype=str)

def _read_lis(file_path, label):
  """
  lisファイルを直接読むroとthd用の関数
  """
  pattern = re.compile(
      re.escape(label) + r'\s*=\s*(\S+)',
      re.IGNORECASE
  )

  with open(file_path, encoding='utf-8') as f:
    for line in f:
      match = pattern.search(line)
      if match:
        return match.group(1)

  return None

def _read_printsw(file_path):
  """
  printswファイルを直接読むcmirとovr用の関数
  """
  # HSPICEのingold=2の出力形式
  number = re.compile(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')

  with open(file_path, 'r') as f:
    return [
        row for row in map(str.split, f)
        if len(row) == 3 and all(map(number.fullmatch, row))
    ]

  return None

def _get_ac1():
  """
  1回目のシミュレーション結果からdcgain/gbw/pmを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result.ma0.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  # dcgain/gbw/pmの値を取得
  dcgain_db = df['dcgain_db'].iloc[0]
  if 'failed' in dcgain_db:
    raise ValueError("Simulation for dcgain failed.")
  pm = df['pm'].iloc[0]
  if 'failed' in pm:
    raise ValueError("Simulation for pm failed.")

  return Decimal(dcgain_db), Decimal(pm)

def _get_bw():
  """
  シミュレーション結果からbwを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result.ma1.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  # bwの値を取得
  bw = df['bw'].iloc[0]
  if 'failed' in bw:
    raise ValueError("Simulation for bw failed.")

  return Decimal(bw)

def _get_dc():
  """
  シミュレーション結果からibとpdisちvosを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result.ms2.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  # ibとpdisの値を取得
  ib = df['ib'].iloc[0]
  pdis = df['pdis'].iloc[0]
  vos = df['vos'].iloc[0]

  if 'failed' in ib:
    raise ValueError("Simulation for ib failed.")
  if 'failed' in pdis:
    raise ValueError("Simulation for pdis failed.")
  if 'failed' in vos:
    raise ValueError("Simulation for vos failed.")

  return Decimal(ib), Decimal(pdis), Decimal(vos)

def _get_sr():
  """
  シミュレーション結果からSRを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result.mt3.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  sr = df['sr'].iloc[0]

  if 'failed' in sr:
    raise ValueError("Simulation for SR failed.")

  return Decimal(sr)

def _get_thd():
  """
  シミュレーション結果からTHDを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result.lis')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  thd = _read_lis(file_path, 'total harmonic distortion')
  if thd is None:
    raise ValueError("Could not find THD in the result file.")
  return Decimal(thd)

def _get_ivr():
  """
  シミュレーション結果からivrを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result.printsw2')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  table = _read_printsw(file_path)
  # 1行目 (vin=0) のデータは使わない
  table.pop(0)

  # 誤差が範囲内であるかを示すフラグ
  get_ivr1 = True
  get_ivr2 = True

  # 許容誤差
  tolerance = Decimal('0.05')

  # ivrの初期化
  ivr1 = Decimal('0.0')
  ivr2 = Decimal('0.0')

  for vin, error1, error2 in table:
    if get_ivr1:
      if Decimal(error1) < tolerance:
        ivr1 = Decimal(vin)
      else:
        get_ivr1 = False

    if get_ivr2:
      if Decimal(error2) < tolerance:
        ivr2 = Decimal(vin)
      else:
        get_ivr2 = False
  ivr = min(ivr1, ivr2)

  return ivr


if __name__ == "__main__":
  main()
