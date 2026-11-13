# Connection and streaming lag FAQ

## Does Frame Control lower my streaming lag?

No. Frame Control uses SSH to manage the Frame. SteamVR or Steam Link sends the
game stream. Frame Control does not carry the game stream. It cannot lower your
game-stream ping or fix a stream that stops on the PC. A 40–75 ms ping in a VR
game is not a Frame Control measurement.

You do **not** need the Steam Wireless Adapter to use Frame Control. The app can
connect over Wi-Fi, the Wireless Adapter, or USB if the computer has an SSH
route to the Frame. Use the route that lets the app connect. To improve game
streaming, check the SteamVR or Steam Link connection on the PC and the Frame.
The [wired connection doctor](wired-connection.md) checks only Frame Control's
SSH route. A successful doctor check does not prove that the game stream uses
the cable or has low lag.

## Can I use a USB-A-to-C cable?

A Mac reached the Frame over a USB-C connection on the
`10.86.200.232/29` USB network. That test used a USB-C host port. We have
**not tested a USB-A-to-C cable** with the Frame. A data-capable USB-A-to-C
cable might show a USB network interface on your PC, but this is unknown on
the tested Frame OS and PC hosts. Check whether your PC shows that interface
and whether Frame Control's wired doctor can reach the Frame at
`10.86.200.233`. A charge-only cable cannot carry USB data. You can use Wi-Fi
for Frame Control if the USB route does not work.

## 日本語: 5 ステップで接続

1. [公式リリース](https://github.com/saphid/frame-control/releases/latest)から PC の OS 用ファイルをダウンロードします。Windows は `.exe`、macOS は `.dmg`、Linux は `.AppImage` または `.deb` です。同じリリースの `SHA256SUMS` でファイルを確認してください。
2. PC に Frame Control をインストールして起動します。Windows はスタートメニュー、macOS はアプリケーション、Linux はアプリ一覧から開きます。AppImage の場合は実行権限を付けて開きます。
3. Frame の Steam 設定 → システムで開発者モードを有効にし、開発者設定でユーザーパスワードを設定します。Frame と PC を同じ信頼できるネットワークに接続し、Frame を起こしておきます。
4. PC の Frame Control で **Set Up Connection…** を選びます。Frame が見つからない場合は、Frame の設定で IP アドレスを確認して入力します。macOS では **Devices & connection → + Add a headset…** からアドレスを設定できます。
5. Frame に **Pair new host** が出たら、自分が開始した要求だけを承認します。ペアリングに失敗した場合は、PC のターミナルで開発者モードのパスワードを入力します。接続後、Frame Control に戻って状態を確認します。

Frame Control は管理用の SSH 接続を使います。ゲーム映像は SteamVR / Steam Link が送ります。Frame Control を入れてもゲームの ping は下がりません。無線アダプターは必須ではありません。USB-A-to-C ケーブルで Frame の USB ネットワークが使えるかは、まだ確認できていません。
