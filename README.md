# sd-webui-TIPO-PNGInfo-Restore

[日本語](#日本語)

Restore your prompts from PNG Info correctly, even when you use [z-tipo-extension](https://github.com/KohakuBlueleaf/z-tipo-extension) (TIPO) on a Forge-based Stable Diffusion WebUI.

When you send an image from PNG Info to txt2img, the **Tag Prompt**, the **Natural Language Prompt** and the **ordinary prompt box** all come back exactly as they were when you pressed Generate, together with every TIPO setting.

If you do not use TIPO, the WebUI's own "Send to txt2img" already restores everything and you do not need this extension. It only fills the gaps that appear when TIPO is in use, and does nothing when TIPO is not installed.

---

## Why this exists

For ordinary images, PNG Info and "Send to txt2img" are all you need. With TIPO, however, restoring an image leaves you fixing prompts by hand:

- The Natural Language Prompt is not saved in the image at all, so it cannot come back.
- If you generated with the TIPO checkbox **off** (a common workflow: press "Generate Prompt", switch TIPO off, then generate), TIPO saves nothing, so none of the TIPO boxes or settings come back.
- What you get in the prompt box is the text after TIPO rewrote it, not the text you actually typed.
- Dynamic Prompts syntax such as `{brown hair|blonde hair}` in the Tag Prompt can be broken or dropped by TIPO's own prompt generation.

This extension fixes those four points and nothing else.

---

## What it does

Drop an image on the PNG Info tab and press **Send to txt2img**.

| Box | What comes back |
| --- | --- |
| Prompt (the ordinary one) | Exactly what was in the box when you pressed Generate |
| Tag Prompt | The tags you typed, weights included |
| Natural Language Prompt | The sentences you typed, weights included |
| TIPO settings | Seed, timing, length targets, Ban tags, format, temperature, Top-p, Top-k, model, CPU mode, No formatting |

Press "Generate Prompt" and TIPO starts again from the same restored Tag Prompt and Natural Language Prompt inputs. If you want to use the restored ordinary prompt exactly as restored, turn TIPO off before pressing Generate.

This works whether the TIPO checkbox was on or off when the image was made. The checkbox itself comes back in the same state it was in.

### Dynamic Prompts protection

TIPO rebuilds your tags through an AI model, and `{A|B}` blocks do not reliably survive that. The typical symptom is that every image gets the same choice even though your prompt contains a variant block.

This extension hides each `{...}` block from TIPO before it runs and puts it back, character for character, afterwards. It works for both the "Generate Prompt" button and generation with TIPO on. Nested blocks such as `{a|{b|c}}` are kept as one block.

There are no new buttons or settings. Prompt generation still happens only through TIPO's own "Generate Prompt" button and TIPO's own format settings.

---

## Installation

**Extensions → Install from URL:**

```
https://github.com/seti9585/sd-webui-TIPO-PNGInfo-Restore
```

Then **fully restart** the WebUI. Reload UI is not enough, because the restore is wired up during start-up.

If it is working, the console shows:

```
[TIPO PNG Info Restore Rev8] Source prompt writer patched on txt2img.
[TIPO PNG Info Restore Rev8] Dynamic Prompts protection patched on txt2img.
[TIPO PNG Info Restore Rev8] Infotext restore mapping patched on txt2img.
```

---

## Good to know

- **Older images.** Images made before you installed this extension still get their Tag Prompt, prompt box and settings back, but not their Natural Language Prompt. That text was never saved in the file, so the box is left as it is rather than filled with a guess.
- **Nothing is guessed.** A box is only filled when the image really contains the value. Otherwise it is left untouched.
- **Nothing is rewritten.** The prompt box comes back as one stored string, so weights, line breaks, embeddings, LoRA calls, tag order and the trailing period are all preserved as written.
- **Regenerating with TIPO enabled.** This extension restores the source prompts that were present before TIPO processes them for image generation. If TIPO is still enabled after Send to txt2img, z-tipo processes those restored inputs again. The final effective prompt written to the new image's infotext can therefore differ from the restored prompt, or contain text added by TIPO. This extension does not modify or sanitize that later TIPO output.
- **Other extensions are left alone.** Only the paste entries that TIPO itself registered are replaced. Entries from any other extension, for example NegPiP's "NegPiP Active", are not touched. Items in the image that do not belong to TIPO are also outside this extension's scope.
- **TIPO off, TIPO boxes empty.** If TIPO is off and both the Tag Prompt and the Natural Language Prompt are empty, nothing is recorded, so images unrelated to TIPO keep a clean infotext.
- **Dynamic Prompts timing.** Protection only matters when TIPO's "Upsampling timing" is set to "Before applying other prompt processings". With "After", Dynamic Prompts has already picked one option before TIPO runs.
- **The trailing period** at the end of TIPO's prompt comes from TIPO's format template. It is preserved like everything else, not added or removed here.

---

## Compatibility with future TIPO updates

This extension is written against the **current z-tipo-extension WebUI implementation**. It hooks into two of TIPO's internal functions, `write_infotext()` and `_process()`, and checks the exact number of arguments each one receives before doing anything.

If a future TIPO update changes either of them:

- TIPO itself keeps working normally, and no error is raised.
- The affected feature quietly switches off: either new images stop recording the source prompts (so the Natural Language Prompt will not come back for them), or Dynamic Prompts blocks are no longer protected.
- The console prints a one-time warning, for example:

```
[TIPO PNG Info Restore Rev8] TIPO passed an unexpected argument shape to write_infotext. ...
[TIPO PNG Info Restore Rev8] TIPO _process was called with an unexpected argument shape. ...
```

If the Natural Language Prompt suddenly stops coming back after a TIPO update, check the console for these lines first.

---

## Infotext keys written

| Key | Content |
| --- | --- |
| `TIPO Input Restore Schema` | `3` |
| `TIPO Input Main Prompt` | The prompt box, verbatim |
| `TIPO Input Tag Prompt` | The Tag Prompt box, verbatim |
| `TIPO Input Natural Language Prompt` | The Natural Language Prompt box, verbatim |
| `TIPO Input Settings` | TIPO settings snapshot, only for runs with the TIPO checkbox off |

When TIPO is on, TIPO writes its own `TIPO Parameters`, `TIPO prompt` and `TIPO nl prompt` keys as usual, and they are used as a fallback for older images.

---

## Tested on

- reForge, Python 3.10.11, PyTorch 2.9.0+cu128
- Forge Neo 2.29.2 (`neo` commit `97b26fb404314a11dad7cdde2706da57ea53f4f2`), Python 3.13.12, PyTorch 2.13.0+cu130
- z-tipo-extension main `319be75ed08e237770c31fcfde87cab711f74372`, including the Forge Neo compatibility fix from [PR #125](https://github.com/KohakuBlueleaf/z-tipo-extension/pull/125)
- Model families actually verified: SDXL (Pony / Illustrious) and Anima
- reForge was also tested together with sd-dynamic-prompts and NegPiP

Other model families such as Qwen Image, Krea, FLUX and WAN have not been verified with this extension, so compatibility with them is not claimed here. Original Forge has not been tested with this extension. img2img uses the same code path as txt2img but has not been verified.

---

# 日本語

[English](#sd-webui-tipo-pnginfo-restore)

Forge 系 Stable Diffusion WebUI で [z-tipo-extension](https://github.com/KohakuBlueleaf/z-tipo-extension)（TIPO）を使っていても、PNG Info からプロンプトを正しく復元できるようにする拡張機能です。

PNG Info から txt2img に画像を送ると、**Tag Prompt**・**Natural Language Prompt**・**通常のプロンプト欄**の3つが、Generate を押した時点の状態そのままに戻ります。TIPO の各設定も一緒に戻ります。

TIPO を使っていないなら、WebUI 標準の「Send to txt2img」だけで十分に復元できるので、この拡張機能は不要です。TIPO を使ったときに生じる不足を埋めるためのもので、TIPO が入っていない環境では何もしません。

---

## なぜ作ったか

普通の画像なら、PNG Info と「Send to txt2img」だけで足ります。ところが TIPO を使うと、画像を戻したあとにプロンプトを手で直す必要が出てきます。

- Natural Language Prompt は画像に保存されていないため、戻せません。
- TIPO のチェックを**外して**生成した場合（「Generate Prompt」を押してから TIPO を OFF にして生成する、よくある使い方）、TIPO は何も保存しません。そのため TIPO の欄も設定も戻りません。
- プロンプト欄に戻るのは TIPO が書き換えたあとの文字列で、自分が実際に入力した文字列ではありません。
- Tag Prompt に書いた `{brown hair|blonde hair}` のような Dynamic Prompts の書式が、TIPO のプロンプト生成で壊れたり消えたりすることがあります。

この拡張機能はこの4点だけを解決します。

---

## できること

PNG Info タブに画像を置いて、**Send to txt2img** を押します。

| 欄 | 戻る内容 |
| --- | --- |
| 通常のプロンプト欄 | Generate を押した時点の内容そのまま |
| Tag Prompt | 入力したタグ（強弱指定も含む） |
| Natural Language Prompt | 入力した自然文（強弱指定も含む） |
| TIPO の設定 | Seed、適用タイミング、長さの目標、Ban tags、フォーマット、Temperature、Top-p、Top-k、モデル、CPU 使用、No formatting |

「Generate Prompt」を押せば、復元された Tag Prompt と Natural Language Prompt を入力として TIPO をやり直せます。復元された通常のプロンプト欄をそのまま使って生成したい場合は、Generate を押す前に TIPO を OFF にしてください。

生成時に TIPO のチェックが入っていても外れていても復元できます。チェックボックス自体も、生成したときと同じ状態で戻ります。

### Dynamic Prompts の保護

TIPO はタグを AI モデルに通して組み立て直すため、`{A|B}` の書式がその途中で壊れることがあります。よくある症状は、プロンプトに `{...}` があるのに、毎回同じ選択肢の画像ばかり出るというものです。

この拡張機能は、TIPO が動く前に `{...}` の部分を TIPO から隠し、終わったあとに1文字も変えずに元へ戻します。「Generate Prompt」ボタンにも、TIPO を ON にしたままの生成にも効きます。`{a|{b|c}}` のような入れ子も、1つのまとまりとして守られます。

新しいボタンや設定は増えません。プロンプト生成は今までどおり、TIPO の「Generate Prompt」ボタンと TIPO 自身のフォーマット設定で行われます。

---

## インストール

**Extensions → Install from URL:**

```
https://github.com/seti9585/sd-webui-TIPO-PNGInfo-Restore
```

インストール後は WebUI を**完全に再起動**してください。復元の仕組みは起動時に組み込まれるので、Reload UI だけでは有効になりません。

正常に動いていれば、コンソールに次のように表示されます。

```
[TIPO PNG Info Restore Rev8] Source prompt writer patched on txt2img.
[TIPO PNG Info Restore Rev8] Dynamic Prompts protection patched on txt2img.
[TIPO PNG Info Restore Rev8] Infotext restore mapping patched on txt2img.
```

---

## 知っておいてほしいこと

- **導入前の画像について。** この拡張機能を入れる前に作った画像でも、Tag Prompt・プロンプト欄・各設定は戻ります。ただし Natural Language Prompt だけは戻りません。そもそもファイルに保存されていないので、推測で埋めずに欄をそのままにします。
- **推測しません。** 画像に値が確かに入っているときだけ欄を埋めます。入っていなければ欄には触れません。
- **書き換えません。** プロンプト欄は保存した1つの文字列としてそのまま戻します。強弱指定、改行、Embedding、LoRA の記述、タグの並び順、末尾のピリオドまで、書いたとおりに戻ります。
- **TIPO を ON にしたまま再生成する場合。** この拡張機能が復元するのは、画像生成時に TIPO が処理する前の元の入力です。Send to txt2img 後も TIPO を ON にして Generate すると、z-tipo が復元された入力を再度処理します。そのため、新しい画像の infotext に記録される最終的な実効プロンプトは、復元されたプロンプトと異なったり、TIPO が追加した文字列を含んだりする場合があります。この拡張機能は、その後の TIPO 出力を書き換えたり補正したりしません。
- **他の拡張機能には触れません。** 置き換えるのは TIPO 自身が登録した貼り付け項目だけです。NegPiP の「NegPiP Active」など、他の拡張機能の項目には手を加えません。画像に含まれる TIPO 以外の項目は、この拡張機能の対象外です。
- **TIPO OFF で入力欄が空の場合。** TIPO が OFF で、Tag Prompt と Natural Language Prompt が両方とも空なら何も記録しません。TIPO と関係のない画像の infotext は汚れません。
- **Dynamic Prompts のタイミング。** 保護が意味を持つのは、TIPO の「Upsampling timing」が「Before applying other prompt processings」のときだけです。「After」の場合は、TIPO が動く前に Dynamic Prompts がすでに1つを選んでいます。
- **末尾のピリオド。** TIPO のプロンプトの最後に付くピリオドは、TIPO のフォーマットのテンプレートに由来します。他の部分と同じくそのまま保つだけで、この拡張機能が付けたり消したりはしません。

---

## 今後の TIPO の更新との互換性

この拡張機能は、**現在の z-tipo-extension（WebUI 版）の実装**に合わせて作っています。TIPO 内部の `write_infotext()` と `_process()` の2つの関数に割り込み、それぞれが受け取る引数の数が想定どおりかを確かめてから動きます。

今後の TIPO の更新でこのどちらかが変わった場合は、次のようになります。

- TIPO 自体は普通に動き、エラーにもなりません。
- 影響を受けた機能だけが静かに止まります。新しく作る画像に元のプロンプトが記録されなくなる（その画像では Natural Language Prompt が戻らなくなる）か、Dynamic Prompts の保護が効かなくなるかのどちらかです。
- コンソールに1回だけ、次のような警告が出ます。

```
[TIPO PNG Info Restore Rev8] TIPO passed an unexpected argument shape to write_infotext. ...
[TIPO PNG Info Restore Rev8] TIPO _process was called with an unexpected argument shape. ...
```

TIPO を更新したあとに Natural Language Prompt が戻らなくなったら、まずコンソールにこの警告が出ていないか確認してください。

---

## 書き込む infotext キー

| キー | 内容 |
| --- | --- |
| `TIPO Input Restore Schema` | `3` |
| `TIPO Input Main Prompt` | プロンプト欄の内容そのまま |
| `TIPO Input Tag Prompt` | Tag Prompt 欄の内容そのまま |
| `TIPO Input Natural Language Prompt` | Natural Language Prompt 欄の内容そのまま |
| `TIPO Input Settings` | TIPO の設定。TIPO を OFF で生成したときだけ記録 |

TIPO が ON のときは、TIPO 自身が `TIPO Parameters`・`TIPO prompt`・`TIPO nl prompt` を今までどおり書き込みます。導入前の画像では、これらを代わりに使って復元します。

---

## 動作確認環境

- reForge、Python 3.10.11、PyTorch 2.9.0+cu128
- Forge Neo 2.29.2（`neo` commit `97b26fb404314a11dad7cdde2706da57ea53f4f2`）、Python 3.13.12、PyTorch 2.13.0+cu130
- z-tipo-extension main `319be75ed08e237770c31fcfde87cab711f74372`（Forge Neo 互換修正 [PR #125](https://github.com/KohakuBlueleaf/z-tipo-extension/pull/125) 取り込み済み）
- 実際に確認したモデル系統は SDXL（Pony / Illustrious）と Anima
- reForge では z-tipo-extension、sd-dynamic-prompts、NegPiP との併用も確認

Qwen Image、Krea、FLUX、WAN など、上記以外のモデル系統ではこの拡張機能の動作確認を行っていないため、README では互換性を保証しません。Original Forge ではこの拡張機能自体の動作確認は行っていません。img2img は txt2img と同じ仕組みで動きますが、動作は未確認です。

---

## License / ライセンス

**MIT License** — Copyright (C) 2026 seti9585

### Acknowledgements / 謝辞

This extension exists only because of [z-tipo-extension](https://github.com/KohakuBlueleaf/z-tipo-extension) and [KGen](https://github.com/KohakuBlueleaf/KGen) by **KohakuBlueleaf**. Sincere thanks.

本拡張機能は、**KohakuBlueleaf** 氏の [z-tipo-extension](https://github.com/KohakuBlueleaf/z-tipo-extension) と [KGen](https://github.com/KohakuBlueleaf/KGen) があってはじめて成り立つものです。深く感謝します。

### Provenance / 典拠

This repository contains original glue code only. No upstream source code is copied or redistributed. The infotext key names, the call signatures of `write_infotext()` and `_process()`, the control order returned by `ui()` and the paste-field registrations were read from the z-tipo-extension source (Apache-2.0) as interface facts; no implementation was taken from it.

本リポジトリに含まれるのは独自の接続コードだけで、上流のソースコードの複製や再配布はしていません。infotext のキー名、`write_infotext()` と `_process()` の引数の形、`ui()` が返すコントロールの順序、貼り付け項目の登録内容は、z-tipo-extension のソース（Apache-2.0）をインターフェースの仕様として参照したものです。実装は取り込んでいません。

References:

- [KohakuBlueleaf/z-tipo-extension](https://github.com/KohakuBlueleaf/z-tipo-extension)
- [KohakuBlueleaf/KGen](https://github.com/KohakuBlueleaf/KGen)
- [adieyal/sd-dynamic-prompts](https://github.com/adieyal/sd-dynamic-prompts)
- [Panchovix/stable-diffusion-webui-reForge](https://github.com/Panchovix/stable-diffusion-webui-reForge)
- [Haoming02/sd-webui-forge-classic](https://github.com/Haoming02/sd-webui-forge-classic)
