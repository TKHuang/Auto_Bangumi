import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { useState } from 'react';

interface Episode {
  id: number;
  title: string;
  time: string;
  cover?: string;
}

interface DaySchedule {
  date: Date;
  dayName: string;
  episodes: Episode[];
}

export default function CalendarPage() {
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());

  const getWeekDays = (): DaySchedule[] => {
    const today = new Date();
    
    const startOfWeek = new Date(today);
    startOfWeek.setDate(today.getDate() - today.getDay());
    
    const days: DaySchedule[] = [];
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    for (let i = 0; i < 7; i++) {
      const d = new Date(startOfWeek);
      d.setDate(startOfWeek.getDate() + i);
      days.push({
        date: d,
        dayName: dayNames[d.getDay()],
        episodes: [
            { id: 1, title: 'Placeholder Anime 1', time: '10:00' },
            { id: 2, title: 'Placeholder Anime 2', time: '14:30' }
        ] 
      });
    }
    return days;
  };

  const weekDays = getWeekDays();

  const isSameDay = (d1: Date, d2: Date) => {
    return d1.getDate() === d2.getDate() && 
           d1.getMonth() === d2.getMonth() && 
           d1.getFullYear() === d2.getFullYear();
  };

  const selectedDaySchedule = weekDays.find(d => isSameDay(d.date, selectedDate)) || weekDays[0];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-bold">Weekly Schedule</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-2 mb-6">
            {weekDays.map((day, i) => {
              const isSelected = isSameDay(day.date, selectedDate);
              const isToday = isSameDay(day.date, new Date());
              
              return (
                <div 
                  key={i} 
                  onClick={() => setSelectedDate(day.date)}
                  className={`
                    cursor-pointer rounded-lg p-3 text-center transition-all border
                    ${isSelected ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-accent border-transparent'}
                    ${isToday && !isSelected ? 'border-primary/50' : ''}
                  `}
                >
                  <div className="text-xs opacity-70 mb-1 uppercase tracking-wider">{day.dayName}</div>
                  <div className="text-lg font-bold">{day.date.getDate()}</div>
                  {day.episodes.length > 0 && (
                    <div className="mt-2 flex justify-center gap-0.5">
                      <div className="h-1.5 w-1.5 rounded-full bg-current opacity-50" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              {selectedDaySchedule.dayName}, {selectedDaySchedule.date.toLocaleDateString()}
              <span className="text-xs font-normal text-muted-foreground bg-secondary px-2 py-0.5 rounded-full">
                {selectedDaySchedule.episodes.length} Airing
              </span>
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {selectedDaySchedule.episodes.map(anime => (
                <div key={anime.id} className="flex items-center gap-4 p-3 rounded-lg border bg-card/50 hover:bg-card transition-colors">
                    <div className="h-12 w-12 rounded bg-muted flex items-center justify-center text-xs text-muted-foreground">
                        IMG
                    </div>
                    <div>
                        <div className="font-medium">{anime.title}</div>
                        <div className="text-sm text-muted-foreground">{anime.time}</div>
                    </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
