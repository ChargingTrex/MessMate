-- ════════════════════════════════════════════════════════════════════════════
-- MessMate — MySQL schema (db/schema.mysql.sql)
-- ════════════════════════════════════════════════════════════════════════════
-- Target: MySQL 8.0.16+ (CHECK constraints are enforced from 8.0.16; tested
-- on 8.4). InnoDB, utf8mb4 throughout, so dish names in Tamil or with emoji
-- store intact.
--
-- Load it into an empty database:
--     mysql -u <user> -p <database> < db/schema.mysql.sql
--
-- This replaces the Google Sheet. Each section names the tab it replaces;
-- the column mapping is in db/README.md. What changes in moving off Sheets:
--
--   * Dates are real DATE / DATETIME columns. The plain-text Date columns and
--     the six-format timestamp parser existed only because Sheets reformats
--     date-looking cells.
--   * The menu is one row per DISH (menu_dishes), not one comma-separated cell
--     per meal, so committee dish ratings can point at the dish they rated.
--   * Rules the app enforces by scanning rows become constraints: one
--     committee review per member per meal per day is a UNIQUE key, and 1-5
--     ratings are CHECKs. A review and its dish ratings go in one transaction,
--     so the orphan-row case sheets.py works around cannot happen.
--   * daily_summary is a VIEW over responses, so it can never drift from the
--     rows it summarises (the Sheets version is an upsert after every submit).
--
-- Times are stored as the app's local wall-clock time, as the Sheet does
-- today (datetime.now()). Run the app and MySQL in the same time zone, or set
-- TZ for both, e.g. Asia/Kolkata.
-- ════════════════════════════════════════════════════════════════════════════

SET NAMES utf8mb4;

-- ── Student per-dish form  (replaces tab: responses) ────────────────────────
-- Anonymous by design: no identity, IP or device column. Keep it that way.
CREATE TABLE responses (
    id             BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    submitted_at   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- A plain column, not GENERATED from submitted_at: MySQL computes a
    -- stored generated column before applying submitted_at's default, so an
    -- insert that relies on the default fails. Write both, or neither.
    submitted_on   DATE             NOT NULL DEFAULT (CURRENT_DATE),
    overall        TINYINT UNSIGNED NOT NULL,
    rice_curry     TINYINT UNSIGNED NULL,     -- NULL = not rated (blank in Sheets)
    rice_rasam     TINYINT UNSIGNED NULL,
    chapati        TINYINT UNSIGNED NULL,
    chapati_gravy  TINYINT UNSIGNED NULL,
    poriyal        TINYINT UNSIGNED NULL,
    sweet          TINYINT UNSIGNED NULL,
    salad          TINYINT UNSIGNED NULL,
    curd           TINYINT UNSIGNED NULL,
    papad          TINYINT UNSIGNED NULL,
    pickle         TINYINT UNSIGNED NULL,
    -- The form caps the review at 150 characters, but the app stores it
    -- html.escape()d, and escaping can grow it (" becomes &quot;).
    review         VARCHAR(1000)    NOT NULL DEFAULT '',
    suggestion     TEXT             NULL,   -- the app sets no server-side cap
    PRIMARY KEY (id),
    KEY idx_responses_day (submitted_on),
    CONSTRAINT chk_responses_day CHECK (submitted_on = DATE(submitted_at)),
    CONSTRAINT chk_responses_overall CHECK (overall BETWEEN 1 AND 5),
    CONSTRAINT chk_responses_items CHECK (
        (rice_curry    IS NULL OR rice_curry    BETWEEN 1 AND 5) AND
        (rice_rasam    IS NULL OR rice_rasam    BETWEEN 1 AND 5) AND
        (chapati       IS NULL OR chapati       BETWEEN 1 AND 5) AND
        (chapati_gravy IS NULL OR chapati_gravy BETWEEN 1 AND 5) AND
        (poriyal       IS NULL OR poriyal       BETWEEN 1 AND 5) AND
        (sweet         IS NULL OR sweet         BETWEEN 1 AND 5) AND
        (salad         IS NULL OR salad         BETWEEN 1 AND 5) AND
        (curd          IS NULL OR curd          BETWEEN 1 AND 5) AND
        (papad         IS NULL OR papad         BETWEEN 1 AND 5) AND
        (pickle        IS NULL OR pickle        BETWEEN 1 AND 5)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ── Daily averages  (replaces tab: daily_summary) ───────────────────────────
-- A view, not a table: always consistent with responses, nothing to upsert.
-- AVG() skips NULLs exactly as calc_avg() skips blanks; COALESCE turns a day
-- with no ratings for an item into 0, as calc_avg() does.
CREATE VIEW daily_summary AS
SELECT
    submitted_on                              AS summary_date,
    ROUND(AVG(overall), 1)                    AS avg_overall,
    COUNT(*)                                  AS response_count,
    COALESCE(ROUND(AVG(rice_curry), 1), 0)    AS avg_rice_curry,
    COALESCE(ROUND(AVG(rice_rasam), 1), 0)    AS avg_rice_rasam,
    COALESCE(ROUND(AVG(chapati), 1), 0)       AS avg_chapati,
    COALESCE(ROUND(AVG(chapati_gravy), 1), 0) AS avg_chapati_gravy,
    COALESCE(ROUND(AVG(poriyal), 1), 0)       AS avg_poriyal,
    COALESCE(ROUND(AVG(sweet), 1), 0)         AS avg_sweet,
    COALESCE(ROUND(AVG(salad), 1), 0)         AS avg_salad,
    COALESCE(ROUND(AVG(curd), 1), 0)          AS avg_curd,
    COALESCE(ROUND(AVG(papad), 1), 0)         AS avg_papad,
    COALESCE(ROUND(AVG(pickle), 1), 0)        AS avg_pickle
FROM responses
GROUP BY submitted_on;


-- ── Food committee roster  (replaces tab: committee_members) ────────────────
-- No DELETE in the app: deactivation (active = 0, term_end set) keeps the
-- review history attached to a real member.
CREATE TABLE committee_members (
    id                    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    email                 VARCHAR(254)  NOT NULL,   -- stored lower-cased
    name                  VARCHAR(120)  NOT NULL,
    password_hash         VARCHAR(255)  NOT NULL,   -- never the plaintext
    active                BOOLEAN       NOT NULL DEFAULT TRUE,
    must_change_password  BOOLEAN       NOT NULL DEFAULT TRUE,
    term_start            DATE          NOT NULL,
    term_end              DATE          NULL,
    created_at            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_committee_members_email (email),
    -- Compared as bytes: under the case-insensitive collation 'A' = 'a'.
    CONSTRAINT chk_committee_members_email_lower
        CHECK (CAST(email AS BINARY) = CAST(LOWER(email) AS BINARY)),
    CONSTRAINT chk_committee_members_term CHECK (term_end IS NULL OR term_end >= term_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ── Published menu  (replaces tab: menu) ────────────────────────────────────
-- One row per (date, meal) that has been published; no row = "Menu not
-- published yet", same as an empty cell today. The dishes live in
-- menu_dishes, in the order staff typed them.
CREATE TABLE menus (
    id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    menu_date   DATE          NOT NULL,
    meal        ENUM('Breakfast', 'Lunch', 'Dinner') NOT NULL,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_menus_date_meal (menu_date, meal)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE menu_dishes (
    id         INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    menu_id    INT UNSIGNED      NOT NULL,
    position   SMALLINT UNSIGNED NOT NULL,   -- 0-based, display order
    dish_name  VARCHAR(120)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_menu_dishes_position (menu_id, position),
    KEY idx_menu_dishes_name (dish_name),
    CONSTRAINT fk_menu_dishes_menu FOREIGN KEY (menu_id)
        REFERENCES menus (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ── Committee reviews  (replaces tab: committee_reviews) ────────────────────
-- One per member per meal per day, enforced by uq_committee_reviews_meal.
-- meal is NULL only for rows imported from before reviews were per meal
-- (blank Meal in the Sheet). NULLs never collide in a MySQL UNIQUE key, so
-- those legacy rows import cleanly.
CREATE TABLE committee_reviews (
    id            BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    member_id     INT UNSIGNED     NOT NULL,
    review_date   DATE             NOT NULL,
    meal          ENUM('Breakfast', 'Lunch', 'Dinner') NULL,
    submitted_at  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    taste         TINYINT UNSIGNED NOT NULL,
    quality       TINYINT UNSIGNED NOT NULL,
    variety       TINYINT UNSIGNED NOT NULL,
    hygiene       TINYINT UNSIGNED NOT NULL,
    menu          TINYINT UNSIGNED NOT NULL,
    review_text   VARCHAR(500)     NOT NULL DEFAULT '',   -- stored raw; Jinja escapes
    PRIMARY KEY (id),
    UNIQUE KEY uq_committee_reviews_meal (member_id, review_date, meal),
    KEY idx_committee_reviews_day (review_date, meal),
    CONSTRAINT fk_committee_reviews_member FOREIGN KEY (member_id)
        REFERENCES committee_members (id) ON DELETE RESTRICT,
    CONSTRAINT chk_committee_reviews_scores CHECK (
        taste   BETWEEN 1 AND 5 AND quality BETWEEN 1 AND 5 AND
        variety BETWEEN 1 AND 5 AND hygiene BETWEEN 1 AND 5 AND
        menu    BETWEEN 1 AND 5
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ── Committee dish ratings  (replaces tab: committee_dish_ratings) ──────────
-- One row per dish the member rated. dish_name is a SNAPSHOT of what the page
-- showed, kept even if the menu is edited later; menu_dish_id links to the
-- live dish while it exists and becomes NULL if that dish is removed.
CREATE TABLE committee_dish_ratings (
    id            BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
    review_id     BIGINT UNSIGNED   NOT NULL,
    position      SMALLINT UNSIGNED NOT NULL,
    menu_dish_id  INT UNSIGNED      NULL,
    dish_name     VARCHAR(120)      NOT NULL,
    rating        TINYINT UNSIGNED  NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_committee_dish_ratings_position (review_id, position),
    KEY idx_committee_dish_ratings_dish (dish_name),
    CONSTRAINT fk_committee_dish_ratings_review FOREIGN KEY (review_id)
        REFERENCES committee_reviews (id) ON DELETE CASCADE,
    CONSTRAINT fk_committee_dish_ratings_dish FOREIGN KEY (menu_dish_id)
        REFERENCES menu_dishes (id) ON DELETE SET NULL,
    CONSTRAINT chk_committee_dish_ratings_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ── Quick meal reactions on /home  (replaces tab: meal_ratings) ─────────────
-- Anonymous like responses. Undo deletes by id rather than by the
-- timestamp + date + meal match the Sheet needs.
CREATE TABLE meal_ratings (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    submitted_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rating_date   DATE            NOT NULL,
    meal          ENUM('Breakfast', 'Lunch', 'Dinner') NOT NULL,
    rating        ENUM('good', 'bad', 'skip') NOT NULL,
    suggestion    VARCHAR(200)    NOT NULL DEFAULT '',
    PRIMARY KEY (id),
    KEY idx_meal_ratings_day (rating_date, meal)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ── Committee analytics helpers ─────────────────────────────────────────────
-- Per-dish committee averages by day and meal: "how did Sambar do at lunch".
CREATE VIEW committee_dish_daily AS
SELECT
    r.review_date,
    r.meal,
    d.dish_name,
    ROUND(AVG(d.rating), 1) AS avg_rating,
    COUNT(*)                AS rating_count
FROM committee_dish_ratings d
JOIN committee_reviews r ON r.id = d.review_id
GROUP BY r.review_date, r.meal, d.dish_name;
