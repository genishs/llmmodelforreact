import React, { useState } from 'react';
import Modal from './Modal';
import { formatDate } from '../utils/date';

interface EventData {
  title: string;
  date: string;
  description: string;
}

interface EventCardProps {
  event: EventData;
}

function EventCard({ event }: EventCardProps) {
  const [open, setOpen] = useState<boolean>(false);
  return (
    <div className="event-card">
      <h3>{event.title}</h3>
      <span>{formatDate(event.date)}</span>
      <button onClick={() => setOpen(true)}>상세</button>
      {open && <Modal onClose={() => setOpen(false)}>{event.description}</Modal>}
    </div>
  );
}

export default EventCard;