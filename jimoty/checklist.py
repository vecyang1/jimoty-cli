"""Physical vehicle on-site inspection checklist for Jimoty (jmty.jp) direct pickup (直接引き取り).

Guards the buyer during in-person vehicle pickup with structured, practical inspection steps:
- Category 1: Documents & VIN (match frame number against 廃車申告受付書, check seal on 譲渡証明書, Jibaiseki insurance).
- Category 2: Engine & Cold Start (verify cold cylinder, electric/kick start, smoke color, abnormal engine noise).
- Category 3: Electrical Systems (headlight hi/lo, brake/tail light, turn signals, horn, battery charging).
- Category 4: Chassis, Suspension, Tires & Brakes (front fork seals, tire tread & cracks, brake drag & feel, fuel tank rust).
- Category 5+: Dynamic listing-specific adaptations (2-stroke oil & smoke, 4-stroke FI warning light, non-running rolling check).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
from jimoty.models import ListingDetail


@dataclass
class ChecklistItem:
    """Individual inspection item for the on-site vehicle pickup safety checklist."""

    category: str
    item: str
    description: str
    is_critical: bool = False
    verification_method: str = ""
    warning_signs: str = ""
    status: str = "pending"  # "pending", "passed", "failed", "na"

    def to_dict(self) -> Dict[str, Any]:
        """Convert checklist item to JSON-serializable dictionary."""
        return {
            "category": self.category,
            "item": self.item,
            "description": self.description,
            "is_critical": self.is_critical,
            "verification_method": self.verification_method,
            "warning_signs": self.warning_signs,
            "status": self.status,
        }


def _is_2stroke(detail: Optional[ListingDetail]) -> bool:
    """Detect whether listing is a 2-stroke engine vehicle."""
    if not detail:
        return False
    text = f"{detail.title or ''} {detail.description or ''} {detail.category or ''}".lower()
    return any(k in text for k in ["2スト", "2st", "2サイクル", "２スト", "２サイクル", "two stroke"])


def _is_4stroke_fi(detail: Optional[ListingDetail]) -> bool:
    """Detect whether listing is a 4-stroke FI vehicle."""
    if not detail:
        return False
    text = f"{detail.title or ''} {detail.description or ''}".lower()
    return any(k in text for k in ["4スト", "4st", "4サイクル", "４スト", "fi車", "インジェクション"])


def _is_non_running(detail: Optional[ListingDetail]) -> bool:
    """Detect whether listing is a non-running or junk vehicle."""
    if not detail:
        return False
    text = f"{detail.title or ''} {detail.description or ''}".lower()
    return any(k in text for k in ["不動", "ジャンク", "部品取り", "かからない", "キック降りない", "固着"])


def get_pickup_checklist(detail: Optional[ListingDetail] = None) -> List[ChecklistItem]:
    """Generate complete physical inspection safety checklist for vehicle pickup.

    Args:
        detail: Optional ListingDetail to customize checklist for specific vehicle attributes
                (e.g., 2-stroke oil inspection, 4-stroke FI check, non-running transport check).

    Returns:
        List of ChecklistItem instances grouped into inspection categories.
    """
    items: List[ChecklistItem] = [
        # =====================================================================
        # Category 1: Documents & VIN
        # =====================================================================
        ChecklistItem(
            category="書類・登録・車台番号 (Documents & VIN)",
            item="車台番号（フレーム番号）と登録書類の照合",
            description="ステアリングヘッドパイプまたはフレームの打刻刻印と、廃車申告受付書（または標識交付証明書）の車台番号が完全に一致するか照合する。",
            is_critical=True,
            verification_method="ステムネック部やステップ下の打刻を目視確認し、削り跡や再打刻痕（打刻不正）がないか指で触れて確認。",
            warning_signs="番号不一致、打刻が削られている、または書類なし（盗難車または市役所・陸運局での再登録不可リスク）。",
        ),
        ChecklistItem(
            category="書類・登録・車台番号 (Documents & VIN)",
            item="譲渡証明書の押印および旧所有者情報の記載確認",
            description="譲渡証明書に旧所有者の住所・氏名が正しく記入され、印鑑（認印可）が押印されているか確認する。",
            is_critical=True,
            verification_method="書類の譲渡人欄に記入・捺印があるか確認。代理出品の場合は委任状または所有者との関係を確認。",
            warning_signs="譲渡人欄が空欄、押印がない、または名義人と出品者の説明が著しく矛盾している。",
        ),
        ChecklistItem(
            category="書類・登録・車台番号 (Documents & VIN)",
            item="自賠責保険証明書の原本および有効期限確認",
            description="自賠責保険付き取引の場合、保険証明書の原本があるか、および有効期間の残存を確認する。",
            is_critical=False,
            verification_method="証明書原本の有効期間（満了日）および契約車台番号を確認。ナンバープレート用ステッカーの年号と照合。",
            warning_signs="証明書がコピーのみ、有効期限切れ、または契約車台番号が一致しない。",
        ),
        ChecklistItem(
            category="書類・登録・車台番号 (Documents & VIN)",
            item="キー（純正鍵・スペアキー）の動作・シリンダー確認",
            description="キーでメインイグニッション、シートロック、給油口、ハンドルロックがすべて1本で開閉・施錠できるか確認する。",
            is_critical=False,
            verification_method="すべての鍵穴にキーを差し込み、スムーズに回るかテスト。ガタつきや引っかかりを確認。",
            warning_signs="ドライバー等でのこじ開け痕、別々の鍵によるチグハグな開閉、ハンドルロック施錠不能。",
        ),

        # =====================================================================
        # Category 2: Engine & Cold Start
        # =====================================================================
        ChecklistItem(
            category="エンジン・コールドスタート始動 (Engine & Cold Start)",
            item="コールドスタート（冷間時始動）の確認",
            description="事前に暖機運転されていない冷えた状態（マフラーやシリンダーが冷たい状態）からスムーズに始動するか確認する。",
            is_critical=True,
            verification_method="始動前にマフラーのエキゾーストパイプやシリンダーヘッドに触れ、冷えていることを確認してから始動。",
            warning_signs="到着前にエンジンが暖まっている（冷間始動不良・キャブレター詰まりの隠蔽リスク）、始動に著しく時間を要する。",
        ),
        ChecklistItem(
            category="エンジン・コールドスタート始動 (Engine & Cold Start)",
            item="セルモーター／キックペダルでの始動性確認",
            description="セルボタン一発で勢いよく回るか、キックペダルの圧縮感およびスプリング自力戻りが正常かテストする。",
            is_critical=False,
            verification_method="セルを押してセルモーターの回転音と勢いを確認。キックを踏み下ろして圧縮の重みとスムーズな戻りを確認。",
            warning_signs="セルがカチカチ鳴るだけで回らない、キックがスカスカ（圧縮抜け）または踏んだまま戻らない。",
        ),
        ChecklistItem(
            category="エンジン・コールドスタート始動 (Engine & Cold Start)",
            item="排気煙の色・異臭およびアイドリングの安定性",
            description="始動後、排気ガスに濃い白煙や青煙が出ていないか、アイドリングが安定してストールしないか確認する。",
            is_critical=True,
            verification_method="アイドリングを1〜2分継続し、回転数のブレやエンストがないか観察。スロットルを軽く煽って排煙を確認。",
            warning_signs="4スト車なのに白煙・青煙が立ち込める（オイル上がり／下がり）、アイドリングが保てず即座にエンストする。",
        ),
        ChecklistItem(
            category="エンジン・コールドスタート始動 (Engine & Cold Start)",
            item="エンジン異音（タペット音・カムチェーン・クランク音）の確認",
            description="アイドリング時および回転上昇時に金属打音やガラガラ音がしないか耳を澄ませて確認する。",
            is_critical=False,
            verification_method="シリンダーヘッド付近、クランクケース左右から異音（カチャカチャ、ゴロゴロ、ガラガラ）が出ていないか聴取。",
            warning_signs="規則的な高い金属打音（バルブクリアランス狂い）、深い重低音のゴロゴロ音（クランクベアリング破損）。",
        ),

        # =====================================================================
        # Category 3: Electrical Systems & Lights
        # =====================================================================
        ChecklistItem(
            category="電装系・灯火類 (Electrical Systems & Lights)",
            item="ヘッドライト（Hi / Lo 切替）および光量確認",
            description="ヘッドライトのハイビーム／ロービームの切り替えが正常に作動し、十分な光量があるか確認する。",
            is_critical=False,
            verification_method="スイッチをHi/Loに切り替え、バルブの球切れや接触不良がないか確認。",
            warning_signs="どちらかが点灯しない、スイッチの接触不良で明滅する、レンズの割れや水没曇り。",
        ),
        ChecklistItem(
            category="電装系・灯火類 (Electrical Systems & Lights)",
            item="ブレーキランプ（前後レバー・ペダル連動）およびテールランプ",
            description="常時テールランプが点灯し、フロントブレーキレバーおよびリアブレーキレバー／ペダルの双方でブレーキランプが強く増光点灯するか確認する。",
            is_critical=True,
            verification_method="前ブレーキのみ、後ろブレーキのみをそれぞれ個別に操作し、確実にテールランプが増光するか確認。",
            warning_signs="片側のレバーでブレーキスイッチが反応しない（後続車への追突事故リスク、保安基準不適合）。",
        ),
        ChecklistItem(
            category="電装系・灯火類 (Electrical Systems & Lights)",
            item="前後ウインカー（方向指示器・4箇所）および点滅リレー",
            description="前後左右すべてのウインカーが一定の間隔で正常に点滅するか確認する。",
            is_critical=False,
            verification_method="左右のウインカースイッチを入れ、インジケーターランプおよび車体前後4つのバルブ点滅を確認。",
            warning_signs="点滅しない（点灯しっぱなし）、ハイフラッシャー（球切れまたはリレー異常）、レンズ脱落。",
        ),
        ChecklistItem(
            category="電装系・灯火類 (Electrical Systems & Lights)",
            item="ホーン（警音器）の吹鳴確認",
            description="ホーンボタンを押して、明瞭な警告音が鳴るか確認する（保安基準適合項目）。",
            is_critical=False,
            verification_method="ホーンボタンを短く押し、音量・音質を確認。",
            warning_signs="音が鳴らない、音がかすれている（ホーン本体の錆・故障またはバッテリー劣化）。",
        ),
        ChecklistItem(
            category="電装系・灯火類 (Electrical Systems & Lights)",
            item="バッテリー電圧および電装充電状態の確認",
            description="バッテリーの電圧降下がないか、エンジン回転を上げた際に灯火類が適度に追従し充電されているか確認する。",
            is_critical=False,
            verification_method="キーON時のメーター照明やインジケーター点灯状態、スロットルを開けた際のライト光量変化をチェック。",
            warning_signs="キーONでメーター球が極端に暗い、アクセルを回しても暗いまま（ジェネレーター／レギュレーター故障）。",
        ),

        # =====================================================================
        # Category 4: Chassis, Suspension, Tires & Brakes
        # =====================================================================
        ChecklistItem(
            category="足回り・タイヤ・ブレーキ (Chassis, Suspension, Tires & Brakes)",
            item="フロントフォークのオイル漏れおよびインナー点錆・シール確認",
            description="インナーチューブのストローク部に点錆がないか、ダストシール・オイルシールからフォークオイルが漏れていないか確認する。",
            is_critical=False,
            verification_method="車体を前後に揺すってフロントフォークをストロークさせ、インナーチューブにオイルの油膜・スジが残らないか目視・触手確認。",
            warning_signs="オイルが滴っている、オイルシールがひび割れてグリスまみれ、摺動部に赤錆（シール交換必須）。",
        ),
        ChecklistItem(
            category="足回り・タイヤ・ブレーキ (Chassis, Suspension, Tires & Brakes)",
            item="前後タイヤの残溝（スリップサイン）および経年ひび割れ（オゾンクラック）",
            description="残り溝が十分にあるか（スリップサインが出ていないか）、サイドウォールやトレッド面にひび割れがないか、製造年週を確認する。",
            is_critical=False,
            verification_method="トレッドの溝深さを確認し、タイヤ側面のヒビ割れや4桁のDOT製造年週（例: 2218＝2018年22週）を確認。",
            warning_signs="スリップサイン露出、深い亀裂（バーストの危険）、タイヤ製造後5年以上経過によるゴム硬化。",
        ),
        ChecklistItem(
            category="足回り・タイヤ・ブレーキ (Chassis, Suspension, Tires & Brakes)",
            item="ブレーキレバーの遊び・タッチ感および引きずり（固着）の有無",
            description="前後ブレーキレバーの引きしろ・タッチが適切か、レバーを離した際にブレーキが引きずっていないか確認する。",
            is_critical=True,
            verification_method="センタースタンドを立てて前後輪を手で空転させ、ブレーキ操作後にホイールが抵抗なくスムーズに回り続けるか確認。",
            warning_signs="レバーがグリップまで着いてしまう（ワイヤー伸び／油圧エア噛み）、タイヤが重くて回らない（キャリパー・ドラム固着）。",
        ),
        ChecklistItem(
            category="足回り・タイヤ・ブレーキ (Chassis, Suspension, Tires & Brakes)",
            item="燃料タンク内の錆（給油口からの目視確認）",
            description="燃料タンクキャップを開け、内部に赤錆や錆の粉末・異物が沈殿していないかペンライト等で照らして確認する。",
            is_critical=False,
            verification_method="タンクキャップを開け、内壁・底面を覗き込む。臭いが腐食ガソリン（ワニス臭）でないか確認。",
            warning_signs="茶色い錆粉が浮いている、タンク内壁が茶色くザラザラ、異臭（キャブレター詰まり・燃料ポンプ故障の主因）。",
        ),
        ChecklistItem(
            category="足回り・タイヤ・ブレーキ (Chassis, Suspension, Tires & Brakes)",
            item="フレームの歪み・ステアリングステムのガタつき・転倒傷",
            description="前ブレーキを握って車体を前後に強く揺すり、ステムベアリングにガタがないか、ハンドルが直進時に左右に曲がっていないか確認する。",
            is_critical=True,
            verification_method="フロントタイヤを浮かせて左右にスムーズに切れるか（中央でのカックン引っかかりがないか）、カウル下のフレーム曲がりを目視。",
            warning_signs="前後揺すりでガタガタ動く、ステアリング操作が引っかかる、フレームに再塗装や歪み跡がある。",
        ),
    ]

    # =========================================================================
    # Dynamic Listing-Specific Adaptations
    # =========================================================================
    if detail is not None:
        if _is_2stroke(detail):
            items.append(
                ChecklistItem(
                    category="2ストローク特有点検 (2-Stroke Engine Specifics)",
                    item="2ストローク車特有：分離給油オイル残量および排気白煙・マフラー詰まり確認",
                    description="2ストオイルタンクの残量およびオイル警告灯の点灯確認。暖機後の排気白煙の量とマフラーからの未燃焼オイル飛び散りを確認する。",
                    is_critical=True,
                    verification_method="オイルタンクキャップを開けオイル残量を確認。エンジン始動後にマフラー出口付近のオイル吹き出しや詰まりがないか確認。",
                    warning_signs="オイル切れ（即座に焼き付き発生）、暖機完了後も視界を遮るほどの猛烈な白煙、マフラーカーボン詰まりによるフケ上がりの悪さ。",
                )
            )

        if _is_4stroke_fi(detail):
            items.append(
                ChecklistItem(
                    category="4ストローク・FI特有点検 (4-Stroke & FI Specifics)",
                    item="4ストロークFI車特有：エンジンオイル量・乳化およびFI警告灯の消灯確認",
                    description="オイルレベルゲージでオイル量と汚れ・白濁（水分混入による乳化）を確認し、キーON時の燃料ポンプ作動音とメーターFIチェックランプの消灯を確認する。",
                    is_critical=False,
                    verification_method="オイルゲージを拭き取ってから油面を確認。キーONで「ジー」という燃料ポンプ圧送音と、エンジン始動後のFI警告灯消灯を確認。",
                    warning_signs="オイルがカフェオレ色に白濁（冷却水混入）、オイル量不足、キーONでFI警告灯が点滅・点灯し続ける（電子制御センサーエラー）。",
                )
            )

        if _is_non_running(detail):
            items.append(
                ChecklistItem(
                    category="不動車・積載運搬注意点 (Non-Running & Loading Logistics)",
                    item="不動車・部品取り車：前後タイヤ転動可否および積載用ロープ固定箇所の確認",
                    description="ブレーキ固着やギア噛み込みがなく、押し歩き（軽トラへの積み込み）が可能か車輪の転がり状態を確認する。",
                    is_critical=True,
                    verification_method="車体を手で前後に押し、車輪がスムーズに転がるか確認。ラッシングベルトを掛ける頑丈なフレーム部を確認。",
                    warning_signs="ブレーキが固着して車輪が回らない（大人複数人やドーリーが必要）、ハンドルロックが解除できない。",
                )
            )

        if detail.is_free or detail.price == 0:
            items.append(
                ChecklistItem(
                    category="無料譲渡・合意確認 (0-Yen As-Is Agreement)",
                    item="無料譲渡条件：ノークレーム・ノーリターン（現状渡し）および名義変更期限の相互確認",
                    description="現状渡しの瑕疵担保責任免責、および持ち帰り後の名義変更（または廃車証明書保管）期限を出品者と相互確認する。",
                    is_critical=False,
                    verification_method="出品者と引き渡し書面またはメッセージ上で、引き渡し後のトラブル免責と手続き期日を合意。",
                    warning_signs="手続き期日の未定、名義変更前の自走持ち帰り（事故時の旧所有者責任リスク）。",
                )
            )

    return items


# Convenience alias for contract compatibility
generate_pickup_checklist = get_pickup_checklist


def render_checklist_markdown(
    items: Optional[List[ChecklistItem]] = None,
    detail: Optional[ListingDetail] = None,
) -> str:
    """Render vehicle inspection checklist formatted in GitHub-flavored Markdown.

    Args:
        items: Optional list of ChecklistItem. If None, generated via get_pickup_checklist(detail).
        detail: Optional ListingDetail for contextual headers.

    Returns:
        Formatted Markdown string.
    """
    if items is None:
        items = get_pickup_checklist(detail)

    title_target = detail.title if detail else "バイク・原付 現車確認"
    price_target = detail.price_text if detail else "N/A"
    critical_count = sum(1 for i in items if i.is_critical)

    lines: List[str] = [
        "# 現車確認・直接引き取り 安全点検チェックリスト",
        "",
        f"> **対象車両**: {title_target}  ",
        f"> **提示価格**: {price_target}  ",
        f"> **総点検項目**: 全{len(items)}項目（**うち重要確認項目: {critical_count}項目**）",
        "",
        "※ **【重要】** 印の項目は、法的トラブル（盗難車・名義変更不可）または重大事故に直結する項目です。引き渡し完了前に必ずクリアしてください。",
        "",
    ]

    # Group by category preserving insertion order
    categories: Dict[str, List[ChecklistItem]] = {}
    for item in items:
        categories.setdefault(item.category, []).append(item)

    cat_idx = 1
    for cat_name, cat_items in categories.items():
        lines.append(f"## {cat_idx}. {cat_name}")
        lines.append("")
        for ci in cat_items:
            badge = " **【重要】**" if ci.is_critical else ""
            lines.append(f"- [ ]{badge} **{ci.item}**")
            lines.append(f"  - **点検内容**: {ci.description}")
            if ci.verification_method:
                lines.append(f"  - **確認方法**: {ci.verification_method}")
            if ci.warning_signs:
                lines.append(f"  - **危険兆候**: ⚠️ {ci.warning_signs}")
            lines.append("")
        cat_idx += 1

    lines.append("---")
    lines.append("### 引き取り完了サイン")
    lines.append("- [ ] 登録書類原本の受領を確認（廃車申告受付書・譲渡証明書）")
    lines.append("- [ ] 現金の支払い・領収確認")
    lines.append("- [ ] 積載（または安全確認後の自走）完了")
    lines.append("")

    return "\n".join(lines)


def render_checklist_terminal(
    items: Optional[List[ChecklistItem]] = None,
    detail: Optional[ListingDetail] = None,
) -> str:
    """Render vehicle inspection checklist formatted for terminal stdout.

    Args:
        items: Optional list of ChecklistItem. If None, generated via get_pickup_checklist(detail).
        detail: Optional ListingDetail for contextual headers.

    Returns:
        Formatted terminal text string.
    """
    if items is None:
        items = get_pickup_checklist(detail)

    title_target = detail.title if detail else "バイク・原付 現車確認"
    price_target = detail.price_text if detail else "N/A"
    critical_count = sum(1 for i in items if i.is_critical)

    sep_double = "=" * 78
    sep_single = "-" * 78

    lines: List[str] = [
        sep_double,
        "       現車確認・直接引き取り 安全点検チェックリスト (Jimoty Inspection)",
        sep_double,
        f" 対象車両 : {title_target}",
        f" 提示価格 : {price_target}",
        f" 点検項目 : 全{len(items)}項目 (重要確認: {critical_count}項目)",
        " 記号凡例 : [!] = 重要項目 (法的トラブル・重大事故防止項目)",
        sep_single,
    ]

    categories: Dict[str, List[ChecklistItem]] = {}
    for item in items:
        categories.setdefault(item.category, []).append(item)

    cat_idx = 1
    for cat_name, cat_items in categories.items():
        lines.append(f"\n[{cat_idx}] {cat_name}")
        for ci in cat_items:
            tag = "[!]" if ci.is_critical else "   "
            lines.append(f"  {tag} [ ] {ci.item}")
            lines.append(f"          内容: {ci.description}")
            if ci.verification_method:
                lines.append(f"          確認: {ci.verification_method}")
            if ci.warning_signs:
                lines.append(f"          注意: ⚠️  {ci.warning_signs}")
        cat_idx += 1

    lines.append("\n" + sep_double)
    lines.append(" 引き取り完了チェック:")
    lines.append("  [ ] 登録書類原本（廃車申告受付書・譲渡証明書）を受領した")
    lines.append("  [ ] メインキー・スペアキーを受け取った")
    lines.append("  [ ] 代金の支払い・受け取りを完了した")
    lines.append(sep_double)

    return "\n".join(lines)
