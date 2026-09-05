"""
Applies all URL corrections to career_pages_corrected.csv using three sources:
  1. Auto-extracted correct URLs from homepage_redirect entries in the smart probe
  2. Researched URLs for the 138 companies that had connection/SSL/404 errors
  3. Manual overrides for the remaining non-auto-fixable redirects

Reads career_pages_corrected.csv (already has 96 fixes from first pass),
applies all remaining fixes, and writes career_pages_corrected.csv in place.
"""

from __future__ import annotations

import csv
import pathlib
import urllib.parse

INPUT_CSV_PATH = pathlib.Path(__file__).parent.parent / "jobspy" / "career_pages_corrected.csv"
OUTPUT_CSV_PATH = pathlib.Path(__file__).parent.parent / "jobspy" / "career_pages_corrected.csv"
SMART_PROBE_CSV_PATH = pathlib.Path(__file__).parent.parent / "career_pages_smart_probe_results.csv"

HOMEPAGE_REDIRECT_PATTERN_FIXES: dict[str, str] = {}

RESEARCHED_URL_FIXES: dict[str, str] = {
    "Alaska Air Group": "https://careers.alaskaair.com",
    "Arista Networks": "https://www.arista.com/en/company/careers",
    "AvalonBay Communities": "https://avalonbay.wd5.myworkdayjobs.com/AVBExternal",
    "Confluent": "https://careers.confluent.io/",
    "Egon Zehnder": "https://www.egonzehnder.com/join-us",
    "Erste Group Bank": "https://www.erstegroup.com/en/career",
    "Foxconn": "https://recruit.foxconn.com/",
    "Fresenius Medical Care": "https://www.freseniusmedicalcare.com/en/careers",
    "General Mills": "https://careers.generalmills.com/",
    "Geodis": "https://geodis.com/career",
    "Great-West Lifeco": "https://www.greatwestlifeco.com/careers.html",
    "Hannover Re": "https://www.hannover-re.com/en/career",
    "Hermès International": "https://www.hermes.com/int/en/career/",
    "Hyundai Motor Group": "https://www.hyundai.com/worldwide/en/company/career",
    "Ingersoll Rand": "https://careers.ingersollrand.com/",
    "Insulet Corporation": "https://insulet.wd5.myworkdayjobs.com/insuletcareers",
    "InterContinental Hotels": "https://careers.ihg.com/",
    "Intesa Sanpaolo": "https://jobs.intesasanpaolo.com/",
    "Jabil": "https://careers.jabil.com/",
    "Jane Street Capital": "https://www.janestreet.com/join-jane-street/",
    "JinkoSolar": "https://jinkosolar.us/careers/",
    "KDDI Corporation": "https://www.kddi.com/corporate/recruit/",
    "Kellanova": "https://www.kellanovacareers.com/",
    "Kering": "https://kering.wd3.myworkdayjobs.com/KeringCareers",
    "Kia Corporation": "https://career.kia.com/",
    "Kraft Heinz": "https://careers.kraftheinzcompany.com/",
    "Kroll, LLC": "https://careers.kroll.com/",
    "Kubota Corporation": "https://www.kubota.com/corporate/careers/",
    "Kuehne+Nagel": "https://home.kuehne-nagel.com/careers",
    "LVMH Moët Hennessy": "https://www.lvmh.com/talents/join-us/job-search/",
    "Landstar System": "https://www.landstar.com/careers/",
    "Lasertec Corporation": "https://www.lasertec.co.jp/en/recruit/",
    "Latham & Watkins": "https://www.lw.com/en/careers",
    "Levi Strauss & Co.": "https://levistraussandco.wd5.myworkdayjobs.com/External",
    "Linde plc": "https://www.linde.com/careers",
    "Lockheed Martin": "https://www.lockheedmartinjobs.com/",
    "Marathon Petroleum": "https://mpc.wd1.myworkdayjobs.com/MPCCareers",
    "Marsh McLennan": "https://careers.marshmclennan.com/",
    "Mazars Group": "https://careers.forvismazars.com/",
    "McKinsey & Company": "https://www.mckinsey.com/careers",
    "Meta Platforms": "https://www.metacareers.com/",
    "Millennium Management": "https://www.mlp.com/careers/",
    "Mitsubishi Chemical": "https://us.mitsubishi-chemical.com/careers/",
    "Mitsubishi Heavy Ind.": "https://www.mhi.com/recruit",
    "NTT (Nippon Tel & Tel)": "https://group.ntt/en/careers/",
    "NXP Semiconductors": "https://www.nxp.com/company/careers:CAREERS",
    "NatWest Group": "https://jobs.natwestgroup.com/",
    "NetEase Games": "https://www.neteasegames.com/careers/",
    "Neurocrine Biosciences": "https://neurocrine.wd1.myworkdayjobs.com/Careers",
    "Nippon Express": "https://www.nipponexpress.com/careers/",
    "Nippon Steel Corp.": "https://www.nipponsteel.com/recruit/",
    "Nissan Motor Co.": "https://www.nissanmotor.jobs/",
    "Nomura Holdings": "https://www.nomura.com/careers/",
    "Norwegian Cruise Line": "https://nclh.wd108.myworkdayjobs.com/NCLH_Careers",
    "Olympus Corporation": "https://www.olympus-global.com/careers/",
    "Otsuka Pharmaceutical": "https://www.otsuka.co.jp/en/careers/",
    "PDD Holdings (Temu)": "https://careers.pddglobalhr.com/",
    "PNC Financial": "https://pnc.wd5.myworkdayjobs.com/External",
    "PVH Corp.": "https://careers.pvh.com/",
    "Pearson plc": "https://pearson.jobs/",
    "Pegatron": "https://www.pegatroncorp.com/Careers",
    "PepsiCo": "https://www.pepsicojobs.com/",
    "PetroChina": "https://zhaopin.cnpc.com.cn/",
    "Ping An Insurance": "https://talent.pingan.com/",
    "Point72 Asset Management": "https://point72.com/careers/",
    "Prada Group": "https://www.pradagroup.com/en/people/careers.html",
    "Prudential Financial": "https://jobs.prudential.com/",
    "Prudential plc": "https://www.prudentialplc.com/en/careers",
    "Public Storage": "https://www.publicstoragejobs.com/",
    "Qantas Airways": "https://www.qantas.com/au/en/about-us/careers.html",
    "Qatar Airways": "https://careers.qatarairways.com/",
    "Quanta Computer": "https://hr.quantatw.com/webrecruit/",
    "RELX Group": "https://www.relx.com/careers",
    "Raiffeisen Bank Int.": "https://www.rbinternational.com/en/careers.html",
    "Rapid7": "https://www.rapid7.com/careers/",
    "Raymond James Financial": "https://raymondjames.wd1.myworkdayjobs.com/RaymondJamesCareers",
    "Realtek Semiconductor": "https://recruit.realtek.com/",
    "Regeneron": "https://careers.regeneron.com/",
    "Renault Group": "https://www.renaultgroup.com/en/talents/",
    "Roland Berger": "https://join.rolandberger.com/",
    "Rolls-Royce Holdings": "https://careers.rolls-royce.com/",
    "Roper Technologies": "https://www.ropertech.com/careers/",
    "Royal Caribbean Group": "https://careers.royalcaribbeangroup.com/",
    "SEB (Skandinaviska Enskilda)": "https://sebgroup.com/career",
    "SMBC Group": "https://www.smbcgroup.com/careers/",
    "STMicroelectronics": "https://www.st.com/content/st_com/en/about/careers.html",
    "Saab AB": "https://www.saab.com/career",
    "Samsung Biologics": "https://samsungbiologics.com/careers",
    "Sarepta Therapeutics": "https://www.sarepta.com/careers",
    "Saudi Aramco": "https://www.aramco.com/en/careers",
    "Sega Sammy Holdings": "https://www.segasammy.co.jp/en/recruit/",
    "ServiceNow": "https://careers.servicenow.com/",
    "Seven & i Holdings": "https://careers.7-eleven.com/",
    "Shin-Etsu Chemical": "https://www.shinetsu.co.jp/jp/recruit/",
    "Shockwave Medical": "https://shockwavemedical.com/careers/",
    "Siemens Energy": "https://jobs.siemens-energy.com/",
    "Singtel": "https://jobs.singtel.com/",
    "Sinopec": "http://job.sinopec.com/",
    "Sompo Holdings": "https://www.sompo-hd.com/en/careers/",
    "Southern Copper": "https://southerncoppercorp.com/eng/job-opportunities/",
    "Spencer Stuart": "https://spencerstuart.wd5.myworkdayjobs.com/Spencer_Stuart_External_Careers",
    "Square Enix": "https://www.square-enix-games.com/en_GB/careers",
    "Stanley Black & Decker": "https://www.stanleyblackanddecker.com/careers",
    "State Grid Corp of China": "https://zhaopin.sgcc.com.cn/",
    "Strategy&": "https://www.strategyand.pwc.com/gx/en/careers.html",
    "Swedbank": "https://www.swedbank.com/work-with-us.html",
    "Sysmex Corporation": "https://www.sysmex.com/us/en/careers",
    "TEPCO": "https://www.tepco.co.jp/recruit/career_recruitment/",
    "TSMC": "https://careers.tsmc.com/",
    "TTM Technologies": "https://www.ttm.com/en/careers",
    "Take-Two Interactive": "https://www.take2games.com/careers",
    "Targa Resources": "https://targaresources.referrals.selectminds.com/",
    "TechnipFMC": "https://www.technipfmc.com/en/careers/",
    "Telefónica": "https://www.telefonica.com/en/talent/",
    "Teradata": "https://www.teradata.com/careers",
    "Tokio Marine Holdings": "https://www.tokiomarinehd.com/en/careers/",
    "Tokyo Electron": "https://www.tel.com/careers/",
    "Toronto-Dominion Bank (TD)": "https://jobs.td.com/",
    "Traton Group": "https://traton.com/en/career.html",
    "Trip.com Group": "https://careers.trip.com/",
    "Turkish Airlines": "https://careers.turkishairlines.com/",
    "Ubisoft Entertainment": "https://www.ubisoft.com/en-us/company/careers",
    "Under Armour": "https://careers.underarmour.com/",
    "United Airlines": "https://careers.united.com/",
    "United Parcel Service": "https://www.jobs-ups.com/",
    "Urban Outfitters": "https://www.urbn.com/work-with-us",
    "Vanguard": "https://www.vanguardjobs.com/",
    "Veeam Software": "https://careers.veeam.com/",
    "Virgin Galactic": "https://www.virgingalactic.com/careers",
    "Voestalpine AG": "https://jobs.voestalpine.com/",
    "Volkswagen Group": "https://www.volkswagen-group.com/en/career-336",
    "Wan Hai Lines": "https://www.wanhai.com/",
    "Willis Towers Watson": "https://careers.wtwco.com/",
    "Wistron": "https://www.wistron.com/career",
    "Woolworths Group": "https://careers.woolworthsgroup.com.au/",
    "Wyndham Hotels & Resorts": "https://wynd.wd5.myworkdayjobs.com/External",
    "Yang Ming Marine": "https://www.yangming.com/en-US/about/JobsCareer.aspx",
    "Yusen Logistics": "https://www.yusen-logistics.com/en/careers",
    "AQR Capital Management": "https://careers.aqr.com/",
    "AXA SA": "https://careers.axa.com/",
    "Aon plc": "https://careers.aon.com/",
    "Arcadium Lithium": "https://careers.riotinto.com/",
    "Bandai Namco Holdings": "https://www.bandainamco.co.jp/en/career/",
    "Brown-Forman": "https://jobs.brown-forman.com/",
    "Canva": "https://www.lifeatcanva.com/en/jobs/",
    "Cushman & Wakefield": "https://jobs.cushmanwakefield.com/",
    "GE Aerospace": "https://jobs.gecareers.com/",
    "Geely Auto Group": "https://hr.geely.com/",
    "General Dynamics": "https://www.gd.com/careers",
    "Genmab": "https://www.genmab.com/careers/",
    "IAC Inc.": "https://www.iac.com/careers",
    "Infineon Technologies": "https://www.infineon.com/careers",
    "Informatica": "https://www.informatica.com/company/careers.html",
    "J.B. Hunt Transport": "https://jbhunt.jobs/",
    "Marcus & Millichap": "https://careers.marcusmillichap.com/",
    "Match Group": "https://careers.mtch.com/",
    "MediaTek": "https://www.mediatek.com/careers",
    "MercadoLibre": "https://careers-meli.mercadolibre.com/en",
}


def load_auto_fixable_redirects() -> dict[str, str]:
    """
    Extract auto-fixable homepage redirect corrections from the smart probe CSV.

    A homepage redirect is auto-fixable when the final URL itself contains a
    career-related path or subdomain (careers., jobs., /careers, /jobs, etc.)
    indicating the server revealed the correct URL via the redirect chain.
    """
    career_final_url_pattern = __import__("re").compile(
        r"(careers?\.|jobs?\.|/careers|/jobs|/career|/vacancies|/talent|/work-with-us)",
        __import__("re").IGNORECASE,
    )
    fixes: dict[str, str] = {}
    with open(SMART_PROBE_CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("outcome") != "homepage_redirect":
                continue
            final_url = row.get("final_url", "").strip()
            if final_url and career_final_url_pattern.search(final_url):
                company_name = row["company_name"].strip()
                parsed = urllib.parse.urlparse(final_url)
                clean_url = urllib.parse.urlunparse(
                    (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", "")
                )
                fixes[company_name] = clean_url or final_url
    return fixes


def build_full_corrections() -> dict[str, str]:
    """
    Merge all correction sources into a single company→URL mapping.

    Priority: researched URLs (most carefully verified) > auto-extracted redirect finals.
    """
    auto_fixes = load_auto_fixable_redirects()
    all_fixes: dict[str, str] = {}
    all_fixes.update(auto_fixes)
    all_fixes.update(RESEARCHED_URL_FIXES)
    return all_fixes


def apply_corrections(corrections: dict[str, str]) -> None:
    """
    Read career_pages_corrected.csv, apply all URL corrections, and write it back in place.
    """
    original_rows: list[dict] = []
    fieldnames: list[str] = []
    with open(INPUT_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            original_rows.append(row)

    stats = {"fixed": 0, "already_ok": 0}
    for row in original_rows:
        company_name = row.get("Company Name", "").strip()
        if company_name in corrections:
            old_url = row.get("Direct Career Portal", "")
            new_url = corrections[company_name]
            if old_url != new_url:
                row["Direct Career Portal"] = new_url
                stats["fixed"] += 1
            else:
                stats["already_ok"] += 1

    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(original_rows)

    print(f"Written: {OUTPUT_CSV_PATH}")
    print(f"  New URLs applied: {stats['fixed']}")
    print(f"  Already correct:  {stats['already_ok']}")
    print(f"  Total corrections map size: {len(corrections)}")


def main():
    corrections = build_full_corrections()
    auto_count = len(load_auto_fixable_redirects())
    research_count = len(RESEARCHED_URL_FIXES)
    print(f"Corrections from redirect auto-extraction: {auto_count}")
    print(f"Corrections from research:                 {research_count}")
    print(f"Total unique corrections:                  {len(corrections)}")
    print()
    apply_corrections(corrections)


if __name__ == "__main__":
    main()
