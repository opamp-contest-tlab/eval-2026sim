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
  results = evaluate_sec1_3()

  for key, value in results.items():
    print(f"{key}: {value:.3e}")

def evaluate_sec1_3(port=None):
  """
  一連のシミュレーションを実行する関数
  """
  # 結果を格納する辞書
  results = {}

  # シミュレーション1回目(SR以外)
  return_code = _run_hspice(os.path.join(BASE_DIR, 'sim1.sp'), os.path.join(TMP_DIR, 'result1.lis'), port)
  if return_code != 0:
    # エラーを吐いて終了
    raise RuntimeError(f"HSPICE first time simulation failed with return code {return_code}")

  # 1回目の結果からvp(SR用入力振幅)を取得してファイルに書き出す
  results['vp'] = _set_vp()

  # シミュレーション2回目(SR)
  return_code = _run_hspice(os.path.join(BASE_DIR, 'sim2.sp'), os.path.join(TMP_DIR, 'result2.lis'), port)
  if return_code != 0:
    # エラーを吐いて終了
    raise RuntimeError(f"HSPICE second time simulation failed with return code {return_code}")

  """出力抵抗"""
  results['rosim_raw'] = _get_rosim()
  # 0.1 Ohmでクリップ
  if results['rosim_raw'] < Decimal('0.1') and results['rosim_raw'] >= Decimal('0'):
    results['rosim'] = Decimal('0.1')
  else:
    results['rosim'] = results['rosim_raw']

  """直流利得/利得帯域幅積/位相余裕"""
  results['dcgain_sim'], results['dcgain_db_sim'], results['gbw'], results['pm'] = _get_ac1()

  """直流利得/出力抵抗の補正"""
  r1 = Decimal('1.0e+4')
  r2 = Decimal('1.0e+4')
  beta = Decimal('0.5')
  rl = Decimal('2.0e+4')
  # 利得の真値をHSPICEから取得すると、丸めの都合で2026年度以前の結果と合わなくなります
  dcgain_sim = Decimal('10') ** (results['dcgain_db_sim'] / Decimal('20'))

  try:
    denominator = (Decimal('1') / results['rosim']) - (Decimal('1') / (r1 + r2)) - (beta * dcgain_sim / rl)
    tmp = (Decimal('1') + beta * dcgain_sim) / denominator
    results['ro'] = tmp
    results['dcgain'] = ((rl + tmp) * dcgain_sim) / rl
    if tmp <= Decimal('0'):
      # roが負の値になるときはdcgain_dbをfailedにする
      results['dcgain_db'] = 'failed'
    else:
      results['dcgain_db'] = Decimal('20') * ((rl + tmp) / rl).log10() + results['dcgain_db_sim']
  except (ArithmeticError):
    results['ro'] = 'failed'
    results['dcgain'] = 'failed'
    results['dcgain_db'] = 'failed'

  """消費電流/消費電力"""
  results['ib'], results['pdis'] = _get_ib_pdis()

  """消費電流変動"""
  results['ibr'] = _get_ibr(results['ib'])

  """同相除去比"""
  results['cmrr'] = _get_cmrr()

  """電源電圧除去比"""
  results['psrr'] = _get_psrr()

  """入力換算雑音"""
  results['irn'] = _get_irn()

  """スルーレート"""
  results['sr'] = _get_sr()

  """全高調波歪"""
  results['thd'] = _get_thd()

  """同相入力範囲"""
  results['cmir'], psvoltage = _get_cmir()

  """出力電圧範囲"""
  results['ovr'], _ = _get_ovr()

  """スコアの算出"""
  # 部門1
  dcgain_tmp = min(results['dcgain'], Decimal('1e9')) # DC Gainは180 dBでクリップ
  results['fom1'] = (results['sr'] * results['cmir'] * dcgain_tmp) / results['ib']

  # 部門2
  results['fom2'] = (results['gbw'] * results['pm']) / (results['pdis'] * results['pdis'] * results['ro'] * results['irn'])

  # 部門3
  cmrr_tmp = Decimal('10.0') ** (results['cmrr'] / Decimal('20.0')) # CMRRは真値で評価
  psrr_tmp = Decimal('10.0') ** (results['psrr'] / Decimal('20.0')) # PSRRは真値で評価
  results['fom3'] = (cmrr_tmp * psrr_tmp) / psvoltage

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

def _set_vp():
  """
  1回目のシミュレーション結果からvp(SR用入力振幅)を取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.ms10.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  # 1回目のシミュレーション結果を読み込む
  df = _read_csv(file_path)

  # vpの値を取得
  vp = df['amp'].iloc[0]

  if 'failed' in vp:
    # シミュレーションが失敗している場合は0.1 Vで固定
    vp = '0.1'

  # ファイルに書き出す
  with open(os.path.join(TMP_DIR, 'for_sr.sp'), 'w') as f:
    f.write(f".param vp={vp} ")

  return Decimal(vp)

def _get_rosim():
  """
  1回目のシミュレーション結果からrosimを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.lis')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  rosim = _read_lis(file_path, 'output resistance at v(out)')
  if rosim is None:
    raise ValueError("Could not find output resistance in the result file.")

  return Decimal(rosim)

def _get_ac1():
  """
  1回目のシミュレーション結果からdcgain/gbw/pmを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.ma2.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  # dcgain/gbw/pmの値を取得
  dcgain_sim = df['dcgain'].iloc[0]
  dcgain_db_sim = df['dcgain_db'].iloc[0]
  if 'failed' in dcgain_sim or 'failed' in dcgain_db_sim:
    raise ValueError("Simulation for dcgain failed.")
  gbw = df['gbw'].iloc[0]
  if 'failed' in gbw:
    raise ValueError("Simulation for gbw failed.")
  pm = df['pm'].iloc[0]
  if 'failed' in pm:
    raise ValueError("Simulation for pm failed.")

  return Decimal(dcgain_sim), Decimal(dcgain_db_sim), Decimal(gbw), Decimal(pm)

def _get_ib_pdis():
  """
  1回目のシミュレーション結果からTypicalのibとpdisを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.ms9.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  # ibとpdisの値を取得
  ib = df['ib'].iloc[0]
  pdis = df['pdis'].iloc[0]

  if 'failed' in ib:
    raise ValueError("Simulation for ib failed.")
  if 'failed' in pdis:
    raise ValueError("Simulation for pdis failed.")

  return Decimal(ib), Decimal(pdis)

def _get_ibr(ib_typical):
  """
  1回目のシミュレーション結果からibr(消費電流の変動)[%]を取得する
  """
  # 結果のファイルがあるかを確認
  files = ['result1.ms0.csv', 'result1.ms1.csv', 'result1.ms2.csv']
  for file in files:
    file_path = os.path.join(TMP_DIR, file)
    if not os.path.exists(file_path):
      raise FileNotFoundError(f"Result file {file_path} not found.")

  df0 = _read_csv(os.path.join(TMP_DIR, 'result1.ms0.csv'))
  ib0 = df0['ib']
  df1 = _read_csv(os.path.join(TMP_DIR, 'result1.ms1.csv'))
  ib1 = df1['ib']
  df2 = _read_csv(os.path.join(TMP_DIR, 'result1.ms2.csv'))
  ib2 = df2['ib']

  diff = Decimal('0.0')
  for ib in [ib0, ib1, ib2]:
    for val in ib:
      if 'failed' in val:
        raise ValueError("Simulation for ibr failed.")
      # Typicalのibとの差の絶対値の最大値を求める
      diff = max(diff, abs(Decimal(val) - ib_typical))

  # 百分率に変換
  ibr = (diff / ib_typical) * Decimal('100')

  return ibr

def _get_sr():
  """
  2回目のシミュレーション結果からSRを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result2.mt0.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  sr = df['sr'].iloc[0]

  if 'failed' in sr:
    raise ValueError("Simulation for SR failed.")

  return Decimal(sr)

def _get_thd():
  """
  1回目のシミュレーション結果からTHDを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.lis')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  thd = _read_lis(file_path, 'total harmonic distortion')
  if thd is None:
    raise ValueError("Could not find THD in the result file.")
  return Decimal(thd)

def _get_irn():
  """
  1回目のシミュレーション結果からirnを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.ma3.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  irn = df['irn'].iloc[0]

  if 'failed' in irn:
    raise ValueError("Simulation for irn failed.")

  return Decimal(irn)

def _get_cmrr():
  """
  1回目のシミュレーション結果からcmrrを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.ma6.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  cmrr = df['cmrr'].iloc[0]

  if 'failed' in cmrr:
    raise ValueError("Simulation for cmrr failed.")

  return Decimal(cmrr)

def _get_psrr():
  """
  1回目のシミュレーション結果からpsrrを取得する
  """
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.ma7.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  psrr = df['psrr'].iloc[0]

  if 'failed' in psrr:
    raise ValueError("Simulation for psrr failed.")

  return Decimal(psrr)

def _get_cmir():
  """
  1回目のシミュレーション結果からcmirを取得する
  """
  # psvoltageを取得
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.ms4.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  psvoltage = df['psvoltage'].iloc[0]
  if 'failed' in psvoltage:
    raise ValueError("Simulation for cmir failed.")

  psvoltage = Decimal(psvoltage)
  
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.printsw4')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  table = _read_printsw(file_path)

  # 誤差が範囲内であるかを示すフラグ
  get_cmr1 = True
  get_cmr2 = True

  # 許容誤差
  tolerance = Decimal('0.05')

  # cmrの初期化
  cmr1 = Decimal('0.0')
  cmr2 = Decimal('0.0')

  for vin, error1, error2 in table:
    if get_cmr1:
      if Decimal(error1) < tolerance:
        cmr1 = Decimal(vin)
      else:
        get_cmr1 = False

    if get_cmr2:
      if Decimal(error2) < tolerance:
        cmr2 = Decimal(vin)
      else:
        get_cmr2 = False
  cmir = Decimal('0.5') * (cmr1 + cmr2) / psvoltage * Decimal('100')

  return cmir, psvoltage

def _get_ovr():
  """
  1回目のシミュレーション結果からovrを取得する
  """
  # psvoltageを取得
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.ms8.csv')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  df = _read_csv(file_path)

  psvoltage = df['psvoltage'].iloc[0]
  if 'failed' in psvoltage:
    raise ValueError("Simulation for ovr failed.")

  psvoltage = Decimal(psvoltage)
  
  # 結果のファイルがあるかを確認
  file_path = os.path.join(TMP_DIR, 'result1.printsw8')
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"Result file {file_path} not found.")

  table = _read_printsw(file_path)

  # 誤差が範囲内であるかを示すフラグ
  get_ovr1 = True
  get_ovr2 = True

  # 許容誤差
  tolerance = Decimal('0.05')

  # ovrの初期化
  ovr1 = Decimal('0.0')
  ovr2 = Decimal('0.0')

  for vin, error1, error2 in table:
    if get_ovr1:
      if Decimal(error1) < tolerance:
        ovr1 = Decimal(vin)
      else:
        get_ovr1 = False

    if get_ovr2:
      if Decimal(error2) < tolerance:
        ovr2 = Decimal(vin)
      else:
        get_ovr2 = False
  ovr = (ovr1 + ovr2) / psvoltage * Decimal('100')

  return ovr, psvoltage


if __name__ == "__main__":
  main()
