# 2026年 演算増幅器設計コンテスト シミュレーションの部 評価システム

京都工芸繊維大学で開発・実装した2026年 演算増幅器設計コンテスト シミュレーションの部 評価用スクリプトです。

## 環境構築
`environment.yml`からpythonの仮想環境を構築してください。
以下のコマンドで実行できます。

```bash
conda env create -n <仮想環境名> -f environment.yml
conda activate <仮想環境名>
```

部門4の評価実行には環境変数`PTS_SPICE_MODEL`にモデルファイルへの絶対パスを設定する必要があります。


## 使い方
評価スクリプトの本体は`main.py`です。
```bash
python main.py -i <ネットリストが格納されたディレクトリ> -o <結果を保存するディレクトリ> --sec <部門番号> 
```
で実行できます。<br>
末尾に`--cc`をつけるとHSPICEのAdvanced Server/Clientモードを使用します。<br>
`--simset`オプションで使用するテストベンチを変更できます。
デフォルトではKIT側の評価スクリプト`simset`ですが、提出サイト側の挙動(ネットリストの成形に関するバグ以外)を再現した`simsetTIT`も選択可能です。

評価後のレポート作成用スクリプトとして`report.py`を用意しています。
```bash
python report.py
```
でKIT側と提出サイト側の評価結果を一覧にした`report.html`が出力されます。
