
# p1
# ------------------------------------------------------------

# Query 1 time-series analysis
# Dataset: query1_mev_volume.csv
# Last updated: 2026-08-13

# Purpose:
# Descriptive time-series analysis, rolling volatility,
# changepoint detection using PELT, and regime analysis.

# Inputs:
#   fetch/query1_mev_volume.csv


# Required R packages:
#   tidyverse
#   lubridate
#   scales
#   zoo
#   changepoint
#   here



library(tidyverse)
library(lubridate)
library(scales)
library(zoo)
library(changepoint)
library(here)

# ------------------------------------------------------------
# 1. QUERY 1 LOADING
# ------------------------------------------------------------


query1 <- read.csv(
  here("fetch", "query1_mev_volume.csv")
)


# Initial inspection of the dataset
#View(query1)
head(query1)
tail(query1)
str(query1)
summary(query1)
names(query1)
dim(query1)


# ------------------------------------------------------------
# 2. QUERY 1 CLEANING AND FORMATTING
# ------------------------------------------------------------

query1 <- query1 %>%
  mutate(
    # Remove the UTC text and convert the variable to Date format
    date = as.Date(
      ymd_hms(
        str_remove(date, " UTC"),
        tz = "UTC",
        quiet = TRUE
      )
    ),
    
    # Convert numerical columns explicitly
    sandwich_trade_count =
      as.numeric(sandwich_trade_count),
    
    total_sandwich_volume_usd =
      as.numeric(total_sandwich_volume_usd),
    
    unique_sandwich_bots =
      as.numeric(unique_sandwich_bots),
    
    unique_transactions =
      as.numeric(unique_transactions)
  ) %>%
  arrange(date)


# Inspect the cleaned dataset
#View(query1)
str(query1)
summary(query1)


# ------------------------------------------------------------
# 3. DATA-QUALITY CHECKS
# ------------------------------------------------------------

# Count missing values in each column
missing_values <- colSums(is.na(query1))

print(missing_values)


# Check whether any dates failed to convert
failed_date_conversions <- sum(is.na(query1$date))

cat(
  "Number of dates that failed to convert:",
  failed_date_conversions,
  "\n"
)


# Check for duplicate dates
duplicate_dates <- query1 %>%
  count(date) %>%
  filter(n > 1)

print(duplicate_dates)


# Check whether any numerical variables contain negative values
negative_value_check <- query1 %>%
  summarise(
    negative_trade_counts =
      sum(sandwich_trade_count < 0, na.rm = TRUE),
    
    negative_volume_values =
      sum(total_sandwich_volume_usd < 0, na.rm = TRUE),
    
    negative_bot_counts =
      sum(unique_sandwich_bots < 0, na.rm = TRUE),
    
    negative_transaction_counts =
      sum(unique_transactions < 0, na.rm = TRUE)
  )

print(negative_value_check)


# ------------------------------------------------------------
# 4. MISSING CALENDAR DAYS CHECK
# ------------------------------------------------------------

all_dates <- tibble(
  date = seq(
    min(query1$date, na.rm = TRUE),
    max(query1$date, na.rm = TRUE),
    by = "day"
  )
)

missing_dates <- all_dates %>%
  anti_join(
    query1,
    by = "date"
  )

print(missing_dates)

cat(
  "Number of missing calendar days:",
  nrow(missing_dates),
  "\n"
)


# ------------------------------------------------------------
# 5. VARIABLES FOR THE TIME-SERIES ANALYSIS
# ------------------------------------------------------------

query1 <- query1 %>%
  mutate(
    year = year(date),
    
    quarter = quarter(
      date,
      with_year = TRUE
    ),
    
    month = floor_date(
      date,
      unit = "month"
    ),
    
    week = floor_date(
      date,
      unit = "week"
    ),
    
    day_of_week = wday(
      date,
      label = TRUE,
      abbr = FALSE
    ),
    
    # Natural logarithm of daily volume.
    # log1p can handle observations equal to zero.
    log_volume =
      log1p(total_sandwich_volume_usd),
    
    # Absolute daily change in USD volume
    daily_change_usd =
      total_sandwich_volume_usd -
      lag(total_sandwich_volume_usd),
    
    # Daily percentage change
    daily_percentage_change =
      (
        total_sandwich_volume_usd /
          lag(total_sandwich_volume_usd) -
          1
      ) * 100,
    
    # Daily logarithmic change
    log_change =
      log_volume -
      lag(log_volume),
    
    # Volume per sandwich-bot trade
    average_volume_per_trade_usd =
      if_else(
        sandwich_trade_count > 0,
        total_sandwich_volume_usd /
          sandwich_trade_count,
        NA_real_
      ),
    
    # Volume per active bot
    average_volume_per_bot_usd =
      if_else(
        unique_sandwich_bots > 0,
        total_sandwich_volume_usd /
          unique_sandwich_bots,
        NA_real_
      ),
    
    # Bot trades per transaction
    trades_per_transaction =
      if_else(
        unique_transactions > 0,
        sandwich_trade_count /
          unique_transactions,
        NA_real_
      )
  )


# ------------------------------------------------------------
# 6. MOVING AVERAGES AND ROLLING VOLATILITY
# ------------------------------------------------------------

query1 <- query1 %>%
  mutate(
    # 7-day moving average
    rolling_mean_7d = rollmean(
      total_sandwich_volume_usd,
      k = 7,
      fill = NA,
      align = "right"
    ),
    
    # 30-day moving average
    rolling_mean_30d = rollmean(
      total_sandwich_volume_usd,
      k = 30,
      fill = NA,
      align = "right"
    ),
    
    # 90-day moving average
    rolling_mean_90d = rollmean(
      total_sandwich_volume_usd,
      k = 90,
      fill = NA,
      align = "right"
    ),
    
    # 30-day rolling standard deviation of daily USD volume
    rolling_sd_30d = rollapply(
      total_sandwich_volume_usd,
      width = 30,
      FUN = sd,
      fill = NA,
      align = "right",
      na.rm = TRUE
    ),
    
    # 30-day rolling mean of daily USD volume
    rolling_average_30d = rollapply(
      total_sandwich_volume_usd,
      width = 30,
      FUN = mean,
      fill = NA,
      align = "right",
      na.rm = TRUE
    ),
    
    # 30-day rolling coefficient of variation
    rolling_cv_30d =
      rolling_sd_30d /
      rolling_average_30d,
    
    # 30-day volatility of daily log changes
    rolling_log_volatility_30d = rollapply(
      log_change,
      width = 30,
      FUN = sd,
      fill = NA,
      align = "right",
      na.rm = TRUE
    )
  )


# ------------------------------------------------------------
# 7. DAILY TIME SERIES PLOT
# ------------------------------------------------------------

daily_volume_plot <- ggplot(
  query1,
  aes(
    x = date,
    y = total_sandwich_volume_usd
  )
) +
  geom_line(
    linewidth = 0.4,
    alpha = 0.65
  ) +
  geom_line(
    aes(y = rolling_mean_30d),
    linewidth = 1
  ) +
  scale_y_continuous(
    labels = label_dollar(
      scale_cut = cut_short_scale()
    )
  ) +
  labs(
    title = "Daily Ethereum Sandwich-Bot Trading Volume",
    subtitle = "Daily volume and 30-day moving average, 2024–2025",
    x = NULL,
    y = "Sandwich-bot trading volume (USD)",
    caption = paste(
      "The variable measures the USD notional volume of sandwich-bot trades,",
      "not necessarily realized MEV profit or victim loss."
    )
  ) +
  theme_minimal(base_size = 12)

print(daily_volume_plot)

#Toward the end of 2025, both daily sandwich-bot trading volume and its 30-day 
#moving average increased, indicating that the rise was not limited to isolated
#high-volume days but reflected a broader increase in the recent level of detected sandwich activity.


# ------------------------------------------------------------
# 8. 7-DAY, 30-DAY, AND 90-DAY MOVING AVERAGES PLOT
# ------------------------------------------------------------

moving_average_data <- query1 %>%
  select(
    date,
    rolling_mean_7d,
    rolling_mean_30d,
    rolling_mean_90d
  ) %>%
  pivot_longer(
    cols = -date,
    names_to = "moving_average",
    values_to = "volume_usd"
  ) %>%
  mutate(
    moving_average = recode(
      moving_average,
      rolling_mean_7d = "7-day moving average",
      rolling_mean_30d = "30-day moving average",
      rolling_mean_90d = "90-day moving average"
    )
  )


moving_average_plot <- ggplot(
  moving_average_data,
  aes(
    x = date,
    y = volume_usd,
    color = moving_average
  )
) +
  geom_line(linewidth = 0.8, na.rm = TRUE) +
  scale_y_continuous(
    labels = label_dollar(
      scale_cut = cut_short_scale()
    )
  ) +
  labs(
    title = "Moving Averages of Sandwich-Bot Trading Volume",
    subtitle = "Comparison of 7-day, 30-day, and 90-day moving averages",
    x = NULL,
    y = "Trading volume (USD)",
    color = NULL
  ) +
  theme_minimal(base_size = 12)

print(moving_average_plot)

#The simultaneous rise in the 7-, 30-, and 90-day moving averages toward the end of 2025
#indicates a sustained increase in sandwich-bot trading volume rather than a temporary short-term spike.

# ------------------------------------------------------------
# 9. WEEKLY SUMMARY STATISTICS
# ------------------------------------------------------------

weekly_statistics <- query1 %>%
  group_by(week) %>%
  summarise(
    weekly_volume_usd =
      sum(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    average_daily_volume_usd =
      mean(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    median_daily_volume_usd =
      median(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    weekly_trade_count =
      sum(
        sandwich_trade_count,
        na.rm = TRUE
      ),
    
    average_unique_bots =
      mean(
        unique_sandwich_bots,
        na.rm = TRUE
      ),
    
    days_observed =
      n(),
    
    .groups = "drop"
  )

#View(weekly_statistics)
print(weekly_statistics)

#Weekly sandwich-bot trading volume remained relatively moderate and variable throughout 
#2024 and early 2025, before increasing sharply from spring 2025 and reaching exceptionally 
#high levels during July–August 2025. Activity peaked in the week of 10 August 2025 at 
#approximately $8.1 billion, compared with weekly volumes generally around $1–2.5 billion in 2024. 
#Volumes subsequently declined but remained relatively elevated through much of late 2025.

# ------------------------------------------------------------
# 10. MONTHLY SUMMARY STATISTICS
# ------------------------------------------------------------

monthly_statistics <- query1 %>%
  group_by(month) %>%
  summarise(
    monthly_volume_usd =
      sum(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    average_daily_volume_usd =
      mean(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    median_daily_volume_usd =
      median(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    monthly_trade_count =
      sum(
        sandwich_trade_count,
        na.rm = TRUE
      ),
    
    average_daily_trade_count =
      mean(
        sandwich_trade_count,
        na.rm = TRUE
      ),
    
    average_unique_bots =
      mean(
        unique_sandwich_bots,
        na.rm = TRUE
      ),
    
    maximum_daily_volume_usd =
      max(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    standard_deviation_usd =
      sd(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    days_observed =
      n(),
    
    .groups = "drop"
  )

#View(monthly_statistics)
print(monthly_statistics)
print(monthly_statistics, n = Inf)

#Consistent with the weekly results, the monthly statistics show a substantial 
#increase in sandwich-bot trading volume beginning in spring 2025, followed by 
#particularly strong growth during July and August. Monthly volume peaked at 
#approximately $31.3 billion in August 2025, confirming that the high weekly 
#volumes observed during this period reflected a sustained increase rather than 
#isolated weekly spikes. Activity subsequently declined, although volumes generally 
#remained above 2024 levels through the end of 2025.

# ------------------------------------------------------------
# 11. MONTHLY SANDWICH-BOT TRADING VOLUME PLOT
# ------------------------------------------------------------

monthly_volume_plot <- ggplot(
  monthly_statistics,
  aes(
    x = month,
    y = monthly_volume_usd
  )
) +
  geom_col() +
  scale_y_continuous(
    labels = label_dollar(
      scale_cut = cut_short_scale()
    )
  ) +
  labs(
    title = "Monthly Sandwich-Bot Trading Volume",
    x = NULL,
    y = "Monthly trading volume (USD)"
  ) +
  theme_minimal(base_size = 12)

print(monthly_volume_plot)

#The monthly trading volume plot shows a sharp increase in sandwich-bot activity during
#mid-2025, peaking in August, followed by a decline toward the end of the year while 
#remaining generally above 2024 levels.

# ------------------------------------------------------------
# 12. ANNUAL AND ANNUALIZED STATISTICS
# ------------------------------------------------------------

annual_statistics <- query1 %>%
  group_by(year) %>%
  summarise(
    first_observation =
      min(date, na.rm = TRUE),
    
    last_observation =
      max(date, na.rm = TRUE),
    
    observed_days =
      sum(
        !is.na(total_sandwich_volume_usd)
      ),
    
    total_volume_usd =
      sum(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    average_daily_volume_usd =
      mean(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    median_daily_volume_usd =
      median(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    minimum_daily_volume_usd =
      min(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    maximum_daily_volume_usd =
      max(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    standard_deviation_usd =
      sd(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    coefficient_of_variation =
      standard_deviation_usd /
      average_daily_volume_usd,
    
    total_trade_count =
      sum(
        sandwich_trade_count,
        na.rm = TRUE
      ),
    
    average_daily_trade_count =
      mean(
        sandwich_trade_count,
        na.rm = TRUE
      ),
    
    average_daily_unique_bots =
      mean(
        unique_sandwich_bots,
        na.rm = TRUE
      ),
    
    # Annualized estimate based on the average observed day
    annualized_volume_usd =
      average_daily_volume_usd * 365.25,
    
    .groups = "drop"
  )

#View(annual_statistics)
print(annual_statistics)


#Compared with 2024, 2025 saw a substantial increase in sandwich-bot trading volume, 
#with total volume rising from $88.9 billion to $158.4 billion and average daily volume 
#from $242.9 million to $434.1 million, while the number of trades and active bots declined, 
#suggesting higher trading volume was concentrated in fewer trades and among fewer active bots.


# Create a formatted annual table for easier reading
annual_statistics_formatted <- annual_statistics %>%
  mutate(
    across(
      ends_with("_usd"),
      ~ dollar(
        .x,
        accuracy = 1,
        big.mark = ","
      )
    ),
    
    coefficient_of_variation =
      round(
        coefficient_of_variation,
        3
      ),
    
    average_daily_unique_bots =
      round(
        average_daily_unique_bots,
        2
      )
  )

#View(annual_statistics_formatted)
print(annual_statistics_formatted)


# ------------------------------------------------------------
# 13. COMPUTE STATISTICS FOR THE FULL SAMPLE
# ------------------------------------------------------------

overall_statistics <- query1 %>%
  summarise(
    start_date =
      min(date, na.rm = TRUE),
    
    end_date =
      max(date, na.rm = TRUE),
    
    number_of_days =
      sum(
        !is.na(total_sandwich_volume_usd)
      ),
    
    total_volume_usd =
      sum(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    average_daily_volume_usd =
      mean(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    median_daily_volume_usd =
      median(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    minimum_daily_volume_usd =
      min(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    maximum_daily_volume_usd =
      max(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    standard_deviation_usd =
      sd(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    coefficient_of_variation =
      standard_deviation_usd /
      average_daily_volume_usd,
    
    total_trade_count =
      sum(
        sandwich_trade_count,
        na.rm = TRUE
      ),
    
    average_daily_trade_count =
      mean(
        sandwich_trade_count,
        na.rm = TRUE
      ),
    
    average_daily_unique_bots =
      mean(
        unique_sandwich_bots,
        na.rm = TRUE
      ),
    
    annualized_volume_usd =
      average_daily_volume_usd * 365.25
  )

#View(overall_statistics)
print(overall_statistics)


# ------------------------------------------------------------
# 14. VOLATILITY STATISTICS
# ------------------------------------------------------------

volatility_statistics <- query1 %>%
  summarise(
    mean_daily_volume_usd =
      mean(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    sd_daily_volume_usd =
      sd(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    coefficient_of_variation =
      sd_daily_volume_usd /
      mean_daily_volume_usd,
    
    mean_daily_change_usd =
      mean(
        daily_change_usd,
        na.rm = TRUE
      ),
    
    mean_absolute_daily_change_usd =
      mean(
        abs(daily_change_usd),
        na.rm = TRUE
      ),
    
    sd_daily_change_usd =
      sd(
        daily_change_usd,
        na.rm = TRUE
      ),
    
    mean_daily_percentage_change =
      mean(
        daily_percentage_change,
        na.rm = TRUE
      ),
    
    sd_daily_percentage_change =
      sd(
        daily_percentage_change,
        na.rm = TRUE
      ),
    
    mean_log_change =
      mean(
        log_change,
        na.rm = TRUE
      ),
    
    sd_log_change =
      sd(
        log_change,
        na.rm = TRUE
      )
  )

#View(volatility_statistics)
print(volatility_statistics)


#Daily sandwich-bot trading volume averaged approximately $338.3 million, with a standard deviation of
#$216.3 million and a coefficient of variation of 0.64, indicating substantial variability relative to 
#the average level of activity. The average absolute day-to-day change was approximately $87.0 million, 
#further showing considerable daily fluctuations in trading volume.

#mean_daily_change_usd ≈ $131,455 is close to zero because positive and negative daily changes 
#cancel each other. It should not be interpreted as low volatility.

# ------------------------------------------------------------
# 15. PLOT 30-DAY ROLLING STANDARD DEVIATION
# ------------------------------------------------------------
# How large are fluctuations in USD?

rolling_sd_plot <- ggplot(
  query1,
  aes(
    x = date,
    y = rolling_sd_30d
  )
) +
  geom_line(linewidth = 0.7) +
  scale_y_continuous(
    labels = label_dollar(
      scale_cut = cut_short_scale()
    )
  ) +
  labs(
    title = "30-Day Rolling Volatility of Sandwich-Bot Trading Volume",
    subtitle = "Rolling standard deviation of daily USD trading volume",
    x = NULL,
    y = "30-day standard deviation (USD)"
  ) +
  theme_minimal(base_size = 12)

print(rolling_sd_plot)

#Absolute volatility increased substantially during mid-2025, although further analysis is required to 
#determine whether this reflects greater relative instability, the higher overall level of trading volume, 
#or a shift between distinct activity regimes.

# ------------------------------------------------------------
# 16. 30-DAY ROLLING COEFFICIENT OF VARIATION PLOT
# ------------------------------------------------------------
#How large are fluctuations relative to the average volume level?

#Did sandwich-bot trading volume become more volatile relative to its average level, or was the increase
#in absolute volatility mainly driven by the higher trading volumes observed in 2025?

#A higher standard deviation might occur simply because the amounts being traded became larger.

rolling_cv_plot <- ggplot(
  query1,
  aes(
    x = date,
    y = rolling_cv_30d
  )
) +
  geom_line(linewidth = 0.7) +
  labs(
    title = "30-Day Rolling Coefficient of Variation",
    subtitle = "Volatility relative to the 30-day average volume",
    x = NULL,
    y = "Coefficient of variation"
  ) +
  theme_minimal(base_size = 12)

print(rolling_cv_plot)

#The increase in absolute volatility during mid-2025 cannot be 
#attributed solely to higher trading volumes, as the coefficient 
#of variation also rose substantially in July. However, relative 
#volatility subsequently declined during August despite exceptionally 
#high trading volumes, suggesting that high activity did not necessarily 
#correspond to proportionally greater instability.

#high volume and high absolute volatility do not automatically mean high relative volatility.

#The decline in relative volatility during August 2025, despite persistently high trading volumes, 
#suggests that elevated sandwich-bot activity became more consistent rather than being driven solely 
#by sporadic high-volume days.

# ------------------------------------------------------------
# 17. VOLATILITY OF DAILY LOG CHANGES PLOT
# ------------------------------------------------------------
# How unstable are day-to-day proportional changes?

rolling_log_volatility_plot <- ggplot(
  query1,
  aes(
    x = date,
    y = rolling_log_volatility_30d
  )
) +
  geom_line(linewidth = 0.7) +
  labs(
    title = "30-Day Volatility of Daily Log Changes",
    subtitle = "Rolling standard deviation of daily log volume changes",
    x = NULL,
    y = "Standard deviation of log changes"
  ) +
  theme_minimal(base_size = 12)

print(rolling_log_volatility_plot)

#In early/mid-2025, log-change volatility was relatively low. For example, during April–May it was often around 0.23–0.25. 
#It then increased during July, reaching about 0.40, meaning day-to-day proportional movements became more variable during 
#the period when volume was rising rapidly.

#It then declined during August to roughly 0.29–0.32, supporting what CV analysis suggested: 
#once trading volume reached very high levels, the day-to-day proportional movements became more stable for a while.

#Another important period: November 2025. Log-change volatility rises sharply, reaching approximately 0.46 around November 10, 
#despite overall trading volume having already fallen substantially from its August peak.


# ------------------------------------------------------------
# 18. DAYS WITH THE HIGHEST TRADING VOLUME
# ------------------------------------------------------------

largest_volume_days <- query1 %>%
  arrange(
    desc(total_sandwich_volume_usd)
  ) %>%
  select(
    date,
    total_sandwich_volume_usd,
    sandwich_trade_count,
    unique_sandwich_bots,
    unique_transactions
  ) %>%
  slice_head(n = 10)

#View(largest_volume_days)
print(largest_volume_days)

#The surge in 2025 sandwich-bot volume was highly concentrated around July and August, 
#with exceptionally large trading volumes being generated by a relatively limited number of 
#active bots and transactions.

#These results indicate that the increase in sandwich-bot 
#trading volume was increasingly concentrated among a smaller 
#number of active bots, a pattern confirmed by the subsequent 
#bot-level distribution and concentration analysis.

# ------------------------------------------------------------
# 19. DAYS WITH THE LARGEST ABSOLUTE CHANGES
# ------------------------------------------------------------

largest_daily_changes <- query1 %>%
  mutate(
    absolute_daily_change_usd =
      abs(daily_change_usd)
  ) %>%
  arrange(
    desc(absolute_daily_change_usd)
  ) %>%
  select(
    date,
    total_sandwich_volume_usd,
    daily_change_usd,
    absolute_daily_change_usd,
    daily_percentage_change
  ) %>%
  slice_head(n = 10)

#View(largest_daily_changes)
print(largest_daily_changes)


# ------------------------------------------------------------
# 20. REGIME SHIFTS DETECTION
# ------------------------------------------------------------

#PELT is used to identify multiple unknown structural changes in the level and variability of sandwich-bot trading volume

#Log volume is used because volume data are often strongly
#right-skewed and may contain very large observations.

regime_data <- query1 %>%
  filter(
    !is.na(date),
    !is.na(log_volume),
    is.finite(log_volume)
  )


#The PELT method detects changes in both the mean and variance
#of the logarithm of daily trading volume.

regime_model <- cpt.meanvar(
  regime_data$log_volume,
  method = "PELT",
  penalty = "MBIC"
)


# Display the model summary
summary(regime_model)

# Note:
# Unlimited maximum changepoints -> reasonable with a penalty such as MBIC.
# Minimum regime of only 2 days -> valid, but potentially too short for the economic interpretation of the data.

# Extract the detected changepoint indices
change_indices <- cpts(regime_model)


# The final observation may be included as a changepoint.
# Remove it because it is not an internal regime shift.

change_indices <- change_indices[
  change_indices < nrow(regime_data)
]


# Convert changepoint indices into dates
regime_shift_dates <- regime_data$date[
  change_indices
]


# Create a table of detected regime shifts
regime_shift_table <- tibble(
  change_number =
    seq_along(regime_shift_dates),
  
  change_date =
    regime_shift_dates
)

#View(regime_shift_table)
print(regime_shift_table)

# These four changepoints divide data into five regimes:
#Regime 1: Jan 2024 → 30 Mar 2025
#Regime 2: 31 Mar → 10 Jul 2025
#Regime 3: 11 Jul → 29 Aug 2025
#Regime 4: 30 Aug → 17 Oct 2025
#Regime 5: 18 Oct → Dec 2025

#Around these dates, the average level and/or variability of log trading volume changed 
#enough for the statistical model to treat the periods before and after as different regimes.


# ------------------------------------------------------------
# 21. ASSIGNING EACH OBSERVATION TO A REGIME
# ------------------------------------------------------------

regime_data <- regime_data %>%
  mutate(
    regime = findInterval(
      seq_len(n()),
      vec = change_indices
    ) + 1
  )


# Inspect the number of observations in each regime
table(regime_data$regime) #counts how many daily observations belong to each regime.

#PELT was allowed to detect very short regimes, but it did not actually do so.

# ------------------------------------------------------------
# 22. SUMMARY STATISTICS FOR EACH REGIME
# ------------------------------------------------------------

regime_summary <- regime_data %>%
  group_by(regime) %>%
  summarise(
    regime_start =
      min(date, na.rm = TRUE),
    
    regime_end =
      max(date, na.rm = TRUE),
    
    number_of_days =
      n(),
    
    average_daily_volume_usd =
      mean(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    median_daily_volume_usd =
      median(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    minimum_daily_volume_usd =
      min(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    maximum_daily_volume_usd =
      max(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    sd_daily_volume_usd =
      sd(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    coefficient_of_variation =
      sd_daily_volume_usd /
      average_daily_volume_usd,
    
    total_volume_usd =
      sum(
        total_sandwich_volume_usd,
        na.rm = TRUE
      ),
    
    average_trade_count =
      mean(
        sandwich_trade_count,
        na.rm = TRUE
      ),
    
    average_unique_bots =
      mean(
        unique_sandwich_bots,
        na.rm = TRUE
      ),
    
    average_unique_transactions =
      mean(
        unique_transactions,
        na.rm = TRUE
      ),
    
    .groups = "drop"
  )

#View(regime_summary)
print(regime_summary)

#Changepoints are the boundary/start of the new regime.

#The PELT analysis identifies a distinct high-volume regime during July–August 2025. 
#The increase in volume occurred despite substantially fewer trades and active bots 
#than in the earlier period, suggesting that the volume surge was associated with 
#larger-volume activity rather than a general increase in the number of sandwich-bot 
#trades or participants. Following the peak regime, trading volume declined, while 
#bot and trade counts continued to fall.



# ------------------------------------------------------------
# 23. PLOT THE DETECTED REGIME SHIFTS
# ------------------------------------------------------------

regime_shift_plot <- ggplot(
  regime_data,
  aes(
    x = date,
    y = total_sandwich_volume_usd
  )
) +
  geom_line(
    linewidth = 0.35,
    alpha = 0.6
  ) +
  geom_smooth(
    aes(group = regime),
    method = "lm",
    formula = y ~ 1,
    se = FALSE,
    linewidth = 1
  ) +
  geom_vline(
    xintercept =
      as.numeric(regime_shift_dates),
    linetype = "dashed",
    linewidth = 0.6
  ) +
  scale_y_continuous(
    labels = label_dollar(
      scale_cut = cut_short_scale()
    )
  ) +
  labs(
    title = "Detected Regimes in Sandwich-Bot Trading Volume",
    subtitle = paste(
      "Dashed vertical lines indicate changepoints detected using the PELT method"
    ),
    x = NULL,
    y = "Daily sandwich-bot trading volume (USD)"
  ) +
  theme_minimal(base_size = 12)

print(regime_shift_plot)


# ------------------------------------------------------------
# 24. PLOT REGIME SHIFTS ON A LOGARITHMIC SCALE
# ------------------------------------------------------------

regime_log_plot <- ggplot(
  regime_data,
  aes(
    x = date,
    y = total_sandwich_volume_usd
  )
) +
  geom_line(
    linewidth = 0.45
  ) +
  geom_vline(
    xintercept =
      as.numeric(regime_shift_dates),
    linetype = "dashed"
  ) +
  scale_y_log10(
    labels = label_dollar(
      scale_cut = cut_short_scale()
    )
  ) +
  labs(
    title = "Sandwich-Bot Trading Volume and Regime Shifts",
    subtitle = "Daily trading volume shown on a logarithmic scale",
    x = NULL,
    y = "Daily trading volume (USD, log scale)"
  ) +
  theme_minimal(base_size = 12)

print(regime_log_plot)


# ------------------------------------------------------------
# 25. COMPARE MEAN VOLUME ACROSS REGIMES
# ------------------------------------------------------------

regime_average_plot <- ggplot(
  regime_summary,
  aes(
    x = factor(regime),
    y = average_daily_volume_usd
  )
) +
  geom_col() +
  scale_y_continuous(
    labels = label_dollar(
      scale_cut = cut_short_scale()
    )
  ) +
  labs(
    title = "Average Daily Sandwich-Bot Volume by Regime",
    x = "Regime",
    y = "Average daily trading volume (USD)"
  ) +
  theme_minimal(base_size = 12)

print(regime_average_plot)


# ------------------------------------------------------------
# 26. EXPORTING TABLES
# ------------------------------------------------------------

write.csv(
  annual_statistics,
  here(
    "output",
    "tables",
    "annual_statistics.csv"
  ),
  row.names = FALSE
)

write.csv(
  overall_statistics,
  here(
    "output",
    "tables",
    "overall_statistics.csv"
  ),
  row.names = FALSE
)



write.csv(
  monthly_statistics,
  here(
    "output",
    "tables",
    "monthly_statistics.csv"
  ),
  row.names = FALSE
)

write.csv(
  volatility_statistics,
  here(
    "output",
    "tables",
    "volatility_statistics.csv"
  ),
  row.names = FALSE
)

write.csv(
  regime_shift_table,
  here(
    "output",
    "tables",
    "regime_shift_table.csv"
  ),
  row.names = FALSE
)


write.csv(
  regime_summary,
  here(
    "output",
    "tables",
    "regime_summary.csv"
  ),
  row.names = FALSE
)



write.csv(
  largest_volume_days,
  here(
    "output",
    "tables",
    "largest_volume_days.csv"
  ),
  row.names = FALSE
)


write.csv(
  largest_daily_changes,
  here(
    "output",
    "tables",
    "largest_daily_changes.csv"
  ),
  row.names = FALSE
)



# ------------------------------------------------------------
# 27. EXPORTING PLOTS
# ------------------------------------------------------------


ggsave(
  filename = here(
    "output",
    "figures",
    "daily_volume_plot.pdf"
  ),
  plot = daily_volume_plot,
  width = 8,
  height = 5
)

ggsave(
  filename = here(
    "output",
    "figures",
    "daily_volume_plot.png"
  ),
  plot = daily_volume_plot,
  width = 8,
  height = 5,
  dpi = 300
)



ggsave(
  filename = here(
    "output",
    "figures",
    "moving_average_plot.pdf"
  ),
  plot = moving_average_plot,
  width = 8,
  height = 5
)

ggsave(
  filename = here(
    "output",
    "figures",
    "moving_average_plot.png"
  ),
  plot = moving_average_plot,
  width = 8,
  height = 5,
  dpi = 300
)



ggsave(
  filename = here(
    "output",
    "figures",
    "monthly_volume_plot.pdf"
  ),
  plot = monthly_volume_plot,
  width = 8,
  height = 5
)

ggsave(
  filename = here(
    "output",
    "figures",
    "monthly_volume_plot.png"
  ),
  plot = monthly_volume_plot,
  width = 8,
  height = 5,
  dpi = 300
)






ggsave(
  filename = here(
    "output",
    "figures",
    "rolling_cv_plot.pdf"
  ),
  plot = rolling_cv_plot,
  width = 8,
  height = 5
)

ggsave(
  filename = here(
    "output",
    "figures",
    "rolling_cv_plot.png"
  ),
  plot = rolling_cv_plot,
  width = 8,
  height = 5,
  dpi = 300
)


ggsave(
  filename = here(
    "output",
    "figures",
    "rolling_sd_plot.pdf"
  ),
  plot = rolling_sd_plot,
  width = 8,
  height = 5
)

ggsave(
  filename = here(
    "output",
    "figures",
    "rolling_sd_plot.png"
  ),
  plot = rolling_sd_plot,
  width = 8,
  height = 5,
  dpi = 300
)

ggsave(
  filename = here(
    "output",
    "figures",
    "rolling_log_volatility_plot.pdf"
  ),
  plot = rolling_log_volatility_plot,
  width = 8,
  height = 5
)

ggsave(
  filename = here(
    "output",
    "figures",
    "rolling_log_volatility_plot.png"
  ),
  plot = rolling_log_volatility_plot,
  width = 8,
  height = 5,
  dpi = 300
)



ggsave(
  filename = here(
    "output",
    "figures",
    "regime_shift_plot.pdf"
  ),
  plot = regime_shift_plot,
  width = 8,
  height = 5
)

ggsave(
  filename = here(
    "output",
    "figures",
    "regime_shift_plot.png"
  ),
  plot = regime_shift_plot,
  width = 8,
  height = 5,
  dpi = 300
)



ggsave(
  filename = here(
    "output",
    "figures",
    "regime_log_plot.pdf"
  ),
  plot = regime_log_plot,
  width = 8,
  height = 5
)

ggsave(
  filename = here(
    "output",
    "figures",
    "regime_log_plot.png"
  ),
  plot = regime_log_plot,
  width = 8,
  height = 5,
  dpi = 300
)


ggsave(
  filename = here(
    "output",
    "figures",
    "regime_average_plot.pdf"
  ),
  plot = regime_average_plot,
  width = 8,
  height = 5
)

ggsave(
  filename = here(
    "output",
    "figures",
    "regime_average_plot.png"
  ),
  plot = regime_average_plot,
  width = 8,
  height = 5,
  dpi = 300
)


