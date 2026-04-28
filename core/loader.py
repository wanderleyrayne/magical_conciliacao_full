from pathlib import Path
import pandas as pd
import unicodedata


SUPPORTED_EXTENSIONS = {".xlsx", ".csv", ".txt"}


def normalize_header_name(value) -> str:
    if value is None:
        return ""

    value = str(value).strip().upper()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = " ".join(value.split())
    return value


def detect_separator(sample: str) -> str:
    if "\t" in sample:
        return "\t"
    if ";" in sample:
        return ";"
    if "," in sample:
        return ","
    return "\t"


def is_header_row(values) -> bool:
    normalized = [normalize_header_name(v) for v in values if str(v).strip()]

    expected = {
        "DATA",
        "LANCAMENTO",
        "RAZAO SOCIAL",
        "CPF/CNPJ",
        "CPF CNPJ",
        "VALOR (R$)",
        "VALOR (RS)",
        "VALOR",
        "SALDO (R$)",
        "SALDO (RS)",
        "DATA PAGAMENTO",
        "DESCRICAO",
        "DESCRIÇÃO",
        "FORMA PAGAMENTO",
        "PAGO",
    }

    hits = sum(1 for item in normalized if item in expected)
    return hits >= 2


def prepare_dataframe_with_detected_header(df_raw: pd.DataFrame) -> pd.DataFrame:
    header_row_index = None

    for idx in range(min(len(df_raw), 15)):
        row_values = df_raw.iloc[idx].tolist()
        if is_header_row(row_values):
            header_row_index = idx
            break

    if header_row_index is None:
        raise ValueError(
            "Não foi possível identificar automaticamente a linha de cabeçalho da planilha."
        )

    header = [str(v).strip() if pd.notna(v) else f"COL_{i}" for i, v in enumerate(df_raw.iloc[header_row_index].tolist())]

    df = df_raw.iloc[header_row_index + 1 :].copy()
    df.columns = header
    df = df.reset_index(drop=True)

    # remove linhas totalmente vazias
    df = df.dropna(how="all")

    # remove colunas totalmente vazias
    df = df.dropna(axis=1, how="all")

    return df


def load_excel_file(path: Path) -> pd.DataFrame:
    df_raw = pd.read_excel(path, header=None)
    return prepare_dataframe_with_detected_header(df_raw)


def load_text_file(path: Path) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        first_chunk = f.read(4096)

    sep = detect_separator(first_chunk)

    df_raw = pd.read_csv(path, sep=sep, header=None, encoding="utf-8-sig", engine="python")
    return prepare_dataframe_with_detected_header(df_raw)


def load_tabular_file(file_path: str) -> pd.DataFrame:
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".xlsx":
        return load_excel_file(path)

    if ext in {".csv", ".txt"}:
        return load_text_file(path)

    raise ValueError(f"Formato não suportado: {ext}")


def summarize_dataframe(df: pd.DataFrame):
    return {
        "linhas": int(df.shape[0]),
        "colunas": int(df.shape[1]),
        "nomes_colunas": list(df.columns.astype(str)),
    }