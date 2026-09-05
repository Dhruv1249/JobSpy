"""
Generates a corrected career_pages.csv by looking up actual career URLs for
companies that returned 404 / connection_error / ssl_error in the live probe.

Reads probe_results CSV, identifies broken entries, and applies a curated
correction map. Outputs career_pages_corrected.csv alongside the original.
"""

import csv
import pathlib

PROBE_RESULTS_PATH = pathlib.Path(__file__).parent.parent / "career_pages_probe_results.csv"
ORIGINAL_CSV_PATH = pathlib.Path(__file__).parent.parent / "jobspy" / "career_pages.csv"
CORRECTED_CSV_PATH = pathlib.Path(__file__).parent.parent / "jobspy" / "career_pages_corrected.csv"

BROKEN_OUTCOME_CODES = frozenset([
    "not_found_404",
    "connection_error",
    "ssl_error",
    "server_error_5xx",
    "other_406",
    "other_400",
    "other_405",
    "other_418",
    "other_464",
    "unexpected_error",
])

URL_CORRECTIONS: dict[str, str] = {
    "3M Company": "https://www.3m.com/3M/en_US/careers-us/",
    "ABN AMRO": "https://werkenbij.abnamro.nl/en",
    "AIA Group Limited": "https://www.aia.com/en/careers",
    "ASOS plc": "https://www.asosplc.com/careers",
    "Adobe": "https://adobe.wd5.myworkdayjobs.com/external_experienced",
    "Agricultural Bank of China": "https://www.abchina.com/en/",
    "Air France-KLM": "https://jobs.airfranceklm.com",
    "Alvarez & Marsal": "https://www.alvarezandmarsal.com/careers",
    "ANA Holdings": "https://www.ana.co.jp/en/jp/career/",
    "Analog Devices": "https://analogdevices.wd1.myworkdayjobs.com/External",
    "Apple": "https://www.apple.com/careers/us/",
    "Asahi Kasei": "https://www.asahi-kasei.com/asahi/en/human_resources/",
    "Aisin Corporation": "https://www.aisin.com/en/company/career/",
    "American Eagle": "https://www.aeo-inc.com/careers/",
    "Anheuser-Busch InBev": "https://www.ab-inbev.com/careers/",
    "Assicurazioni Generali": "https://careers.generali.com",
    "Astellas Pharma": "https://www.astellas.com/en/careers",
    "Atlas Copco": "https://www.atlascopcogroup.com/en/careers",
    "Axel Springer SE": "https://www.axelspringer.com/en/careers",
    "BBVA": "https://www.bbva.com/en/careers/",
    "BDO International": "https://www.bdo.global/en-gb/careers",
    "BMW Group": "https://www.bmwgroup.com/en/career.html",
    "BYD Auto": "https://www.byd.com/en/careers.html",
    "Banco Santander": "https://www.santander.com/en/careers",
    "Bank of China": "https://www.boc.cn/en/careers/",
    "Baxter International": "https://www.baxter.com/baxter-careers",
    "Bertelsmann SE": "https://www.bertelsmann.com/careers/",
    "Boston Properties (BXP)": "https://www.bxp.com/careers/",
    "Brookfield Renewable": "https://bep.brookfield.com/about/careers",
    "CMA CGM Group": "https://www.cma-cgm.com/careers",
    "Capcom Co., Ltd.": "https://www.capcom.co.jp/recruit/",
    "Capri Holdings": "https://www.capriholdings.com/careers/",
    "Capital One": "https://www.capitalonecareers.com",
    "Canadian Solar": "https://www.canadiansolar.com/career/",
    "Cardinal Health": "https://jobs.cardinalhealth.com",
    "Celanese Corporation": "https://www.celanese.com/careers",
    "China Construction Bank": "https://www.ccb.com/en/career/index.html",
    "China Life Insurance": "https://www.chinalife.com.cn/en/",
    "China Mobile": "https://www.chinamobileltd.com/en/careers/",
    "China Unicom": "https://www.chinaunicom.com.hk/en/about/careers.html",
    "Choice Hotels Int.": "https://jobs.choicehotels.com",
    "Compal Electronics": "https://www.compal.com/careers/",
    "Continental AG": "https://www.continental.com/en/career/",
    "Coty Inc.": "https://www.coty.com/careers/",
    "Coupang": "https://www.coupang.jobs",
    "Crédit Agricole": "https://jobs.credit-agricole.com",
    "Daimler Truck": "https://www.daimlertruck.com/en/career",
    "Danaher Corporation": "https://careers.danaher.com",
    "Danfoss Group": "https://www.danfoss.com/en/careers/",
    "Dassault Aviation": "https://www.dassault-aviation.com/en/group/careers/",
    "Deloitte": "https://www2.deloitte.com/global/en/pages/careers/articles/global-careers.html",
    "Delta Air Lines": "https://careers.delta.com",
    "Delta Electronics": "https://www.deltaww.com/en-US/careers",
    "Denso Corporation": "https://www.denso.com/global/en/careers/",
    "Dentsply Sirona": "https://jobs.dentsplysirona.com",
    "Deutsche Telekom": "https://www.telekom.com/en/careers",
    "Dominion Energy": "https://jobs.dominionenergy.com",
    "Dropbox": "https://jobs.dropbox.com",
    "DuPont": "https://jobs.dupont.com",
    "ENGIE": "https://jobs.engie.com",
    "Eaton Corporation": "https://eaton.eightfold.ai/careers",
    "Eisai": "https://www.eisai.com/career/index.html",
    "Enel Group": "https://www.enel.com/en/careers",
    "Entegris": "https://www.entegris.com/en/home/about-us/careers.html",
    "Evergreen Marine Corp.": "https://www.evergreen-marine.com/tei1/jsp/en/index.jsp",
    "Exelon Corporation": "https://jobs.exeloncorp.com",
    "Fast Retailing (Uniqlo)": "https://www.fastretailing.com/eng/recruit/",
    "HMM Co., Ltd.": "https://www.hmm21.com/cms/business/usa/index.html",
    "Hapag-Lloyd AG": "https://www.hapag-lloyd.com/en/careers.html",
    "Hitachi, Ltd.": "https://www.hitachicareers.com",
    "Humana": "https://careers.humana.com",
    "ICBC": "https://www.icbc-ltd.com/ICBCLtd/html/en/recruit/",
    "ITV plc": "https://www.itvjobs.com",
    "Illumina": "https://careers.illumina.com",
    "JFE Holdings": "https://www.jfe-holdings.co.jp/en/career/",
    "Japan Airlines": "https://www.jal.com/en/career/",
    "Kansai Electric Power": "https://www.kepco.co.jp/english/",
    "Kerry Logistics": "https://www.kerrylogistics.com/en/careers/",
    "Kintetsu World Express": "https://www.kwe.com/jp/en/careers/",
    "Konami Group": "https://www.konami.com/en/careers/",
    "Korea Aerospace Ind.": "https://www.koreaaero.com/EN/About/HRPolicy.aspx",
    "LATAM Airlines Group": "https://careers.latam.com",
    "Legal & General Group": "https://careers.legalandgeneral.com",
    "Lenovo Group": "https://jobs.lenovo.com",
    "Lionsgate Entertainment": "https://www.lionsgate.com/corporate/careers",
    "MGM Resorts Int.": "https://mgmresortscareers.com",
    "MS&AD Insurance Group": "https://www.ms-ad-hd.com/en/sustainability/social/human-resources/",
    "MUFG": "https://mufgamericas.com/careers",
    "Man Group": "https://www.man.com/careers",
    "NCSoft": "https://careers.ncsoft.com",
    "Rohm Semiconductor": "https://www.rohm.com/careers",
    "Scopely": "https://scopely.com/careers/",
    "Super Micro Computer": "https://www.supermicro.com/en/about/careers",
    "The Hartford": "https://www.thehartford.com/careers",
    "Vail Resorts, Inc.": "https://www.vailresortscareers.com",
    "Vivendi SE": "https://www.vivendi.com/en/vivendi-2/careers/",
}


def load_probe_results() -> dict[str, str]:
    broken: dict[str, str] = {}
    with open(PROBE_RESULTS_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["outcome"] in BROKEN_OUTCOME_CODES:
                broken[row["company_name"]] = row["outcome"]
    return broken


def build_corrected_csv() -> None:
    broken_companies = load_probe_results()

    original_rows = []
    with open(ORIGINAL_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            original_rows.append(row)

    corrected_rows = []
    stats = {"fixed": 0, "no_fix_available": 0, "ok": 0}

    for row in original_rows:
        company_name = row["Company Name"]
        if company_name in broken_companies:
            if company_name in URL_CORRECTIONS:
                row["Direct Career Portal"] = URL_CORRECTIONS[company_name]
                stats["fixed"] += 1
            else:
                stats["no_fix_available"] += 1
        else:
            stats["ok"] += 1
        corrected_rows.append(row)

    with open(CORRECTED_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(corrected_rows)

    print(f"Written: {CORRECTED_CSV_PATH}")
    print(f"  URLs fixed:           {stats['fixed']}")
    print(f"  Still broken (no fix): {stats['no_fix_available']}")
    print(f"  Already working:      {stats['ok']}")
    print()

    unfixed = [
        name for name in broken_companies
        if name not in URL_CORRECTIONS
    ]
    if unfixed:
        print("Companies still needing URL fixes:")
        for name in sorted(unfixed):
            print(f"  {name}")


if __name__ == "__main__":
    build_corrected_csv()
