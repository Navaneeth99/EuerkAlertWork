library(data.table)

project_dir <- "/Users/schoudhary42/Library/CloudStorage/Dropbox-Personal/Projects/EuerkAlertWork"
doi_path    <- file.path(project_dir, "Processed", "DOIList.csv")
alt_path    <- file.path(project_dir, "rawdata", "AltMetData", "aaas_deliverable_20260415.csv")
out_dir     <- file.path(project_dir, "Processed", "PaperAltMet")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

cat("Reading DOI list...\n")
dois <- fread(doi_path)
cat("  rows:", nrow(dois), " unique DOIs:", uniqueN(dois$doi), "\n")

cat("Reading Altmetric deliverable...\n")
alt_cols <- c("doi",
              "policy_mentions", "patent_mentions", "news_mentions",
              "facebook_mentions", "x_post_mentions", "bluesky_mentions",
              "video_mentions",
              "altmetric_id", "altmetric_details_page_link")
alt <- fread(alt_path, select = alt_cols)
cat("  rows:", nrow(alt), " unique DOIs:", uniqueN(alt$doi), "\n")

# Normalize DOIs (lowercase, trim) for safer matching
dois[, doi_key := tolower(trimws(doi))]
alt[,  doi_key := tolower(trimws(doi))]

# Collapse Altmetric to one row per DOI (in case of dupes), keep first
# Drop the original `doi` from alt to avoid name clash with dois$doi
alt_unique <- alt[!duplicated(doi_key)][, doi := NULL]

# Left join: every DOI from our list, with altmetric where available
merged <- alt_unique[dois, on = "doi_key"]
merged[, doi_key := NULL]

# Reorder columns so identifiers come first
id_cols <- c("entity_name", "openalex_id", "category", "doi", "publication_date")
metric_cols <- setdiff(names(merged), id_cols)
setcolorder(merged, c(id_cols, metric_cols))

# Coverage flags. Every DOI is present in the deliverable; these describe
# *what kind of altmetric coverage* a DOI has, not whether the join matched.
mention_cols <- c("policy_mentions", "patent_mentions", "news_mentions",
                  "facebook_mentions", "x_post_mentions", "bluesky_mentions",
                  "video_mentions")
merged[, has_altmetric_record := !is.na(altmetric_id) & altmetric_id != ""]
merged[, has_any_attention := rowSums(.SD, na.rm = TRUE) > 0, .SDcols = mention_cols]

cat("Writing merged file...\n")
fwrite(merged, file.path(out_dir, "PaperAltMet.csv"))

# ---- Coverage report ---------------------------------------------------------
report <- merged[, .(
    total_dois          = .N,
    with_altmetric_rec  = sum(has_altmetric_record),
    pct_with_record     = round(100 * sum(has_altmetric_record) / .N, 2),
    with_any_attention  = sum(has_any_attention),
    pct_with_attention  = round(100 * sum(has_any_attention) / .N, 2)
), by = .(category, entity_name)][order(category, -total_dois)]

fwrite(report, file.path(out_dir, "coverage_by_entity.csv"))

overall <- merged[, .(
    total_dois          = .N,
    with_altmetric_rec  = sum(has_altmetric_record),
    pct_with_record     = round(100 * sum(has_altmetric_record) / .N, 2),
    with_any_attention  = sum(has_any_attention),
    pct_with_attention  = round(100 * sum(has_any_attention) / .N, 2)
)]

cat("\n=== Overall coverage ===\n")
print(overall)

cat("\n=== Coverage by entity ===\n")
print(report, nrows = 60)

cat("\nOutputs:\n")
cat("  ", file.path(out_dir, "PaperAltMet.csv"), "\n")
cat("  ", file.path(out_dir, "coverage_by_entity.csv"), "\n")
