package markethours

import (
	"fmt"
	"time"
)

type Schedule struct {
	Name      string
	Timezone  string
	OpenHour  int
	OpenMin   int
	CloseHour int
	CloseMin  int
	Days      map[time.Weekday]bool
	Broker    string
}

type Service struct {
	nowFn     func() time.Time
	schedules map[string]Schedule
}

func NewService() *Service {
	return &Service{
		nowFn: time.Now,
		schedules: map[string]Schedule{
			"US": {
				Name:      "US Markets (NYSE/NASDAQ)",
				Timezone:  "America/New_York",
				OpenHour:  9,
				OpenMin:   30,
				CloseHour: 16,
				CloseMin:  0,
				Days: map[time.Weekday]bool{
					time.Monday:    true,
					time.Tuesday:   true,
					time.Wednesday: true,
					time.Thursday:  true,
					time.Friday:    true,
				},
				Broker: "alpaca",
			},
		},
	}
}

func (s *Service) IsMarketOpen(marketID string) bool {
	schedule, ok := s.schedules[marketID]
	if !ok {
		return false
	}
	loc, err := time.LoadLocation(schedule.Timezone)
	if err != nil {
		return false
	}
	now := s.nowFn().In(loc)
	if !schedule.Days[now.Weekday()] {
		return false
	}
	open := time.Date(now.Year(), now.Month(), now.Day(), schedule.OpenHour, schedule.OpenMin, 0, 0, loc)
	closeAt := time.Date(now.Year(), now.Month(), now.Day(), schedule.CloseHour, schedule.CloseMin, 0, 0, loc)
	return (now.Equal(open) || now.After(open)) && (now.Equal(closeAt) || now.Before(closeAt))
}

func (s *Service) IsUSMarketOpen() bool {
	return s.IsMarketOpen("US")
}

func (s *Service) GetNextMarketOpen(marketID string) string {
	schedule, ok := s.schedules[marketID]
	if !ok {
		return "Unknown market"
	}
	if s.IsMarketOpen(marketID) {
		return fmt.Sprintf("Market is currently OPEN (closes at %02d:%02d %s)", schedule.CloseHour, schedule.CloseMin, schedule.Timezone)
	}

	loc, err := time.LoadLocation(schedule.Timezone)
	if err != nil {
		return "Unknown market"
	}
	now := s.nowFn().In(loc)

	beforeOpenToday := schedule.Days[now.Weekday()] &&
		(now.Hour() < schedule.OpenHour || (now.Hour() == schedule.OpenHour && now.Minute() < schedule.OpenMin))
	if beforeOpenToday {
		return fmt.Sprintf("Opens today at %02d:%02d %s", schedule.OpenHour, schedule.OpenMin, schedule.Timezone)
	}

	if now.Weekday() == time.Friday || now.Weekday() == time.Saturday || now.Weekday() == time.Sunday {
		return fmt.Sprintf("Opens Monday at %02d:%02d %s", schedule.OpenHour, schedule.OpenMin, schedule.Timezone)
	}

	return fmt.Sprintf("Opens tomorrow at %02d:%02d %s", schedule.OpenHour, schedule.OpenMin, schedule.Timezone)
}
