import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Calendar,
  Clock,
  Video,
  CheckCircle2,
  XCircle,
  RotateCw,
  ExternalLink,
  AlertTriangle,
  User,
  Building2,
  Mail,
  Edit2,
  CalendarDays,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { LoadingState } from '@/components/ui/FeedbackStates';

interface MeetingItem {
  id: string;
  title: string;
  attendee_name: string;
  attendee_email: string;
  start_time: string;
  end_time: string;
  timezone: string;
  status: string;
  outlook_event_id?: string;
  teams_join_url?: string;
  auto_booked: boolean;
}

interface ProposalItem {
  id: string;
  contact_id: string;
  requested_slot?: string;
  offered_slots: string;
  status: string;
  expires_at: string;
}

interface MeetingsResponse {
  bookings: MeetingItem[];
  proposals: ProposalItem[];
}

export const MeetingsCalendarPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'all' | 'confirmed' | 'proposals'>('all');
  const [selectedMeeting, setSelectedMeeting] = useState<MeetingItem | null>(null);
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('Customer requested cancellation');

  const [isRescheduleModalOpen, setIsRescheduleModalOpen] = useState(false);
  const [newStartDate, setNewStartDate] = useState('');

  // 1. Fetch Meetings
  const { data, isLoading, refetch, isFetching } = useQuery<StandardResponse<MeetingsResponse>>({
    queryKey: ['responder-meetings'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<MeetingsResponse>>('/responder/meetings');
      return res.data;
    },
    refetchInterval: 15000,
  });

  const rawData = data?.data;
  const bookings: MeetingItem[] = Array.isArray(rawData)
    ? rawData
    : (Array.isArray(rawData?.bookings) ? rawData.bookings : []);
  const proposals: ProposalItem[] = Array.isArray(rawData?.proposals)
    ? rawData.proposals
    : [];

  // 2. Cancel Meeting Mutation
  const cancelMutation = useMutation({
    mutationFn: async ({ meetingId, reason }: { meetingId: string; reason: string }) => {
      return apiClient.post(`/responder/meetings/${meetingId}/cancel`, { reason });
    },
    onSuccess: () => {
      setIsCancelModalOpen(false);
      setSelectedMeeting(null);
      queryClient.invalidateQueries({ queryKey: ['responder-meetings'] });
      queryClient.invalidateQueries({ queryKey: ['responder-dashboard'] });
    },
  });

  // 3. Reschedule Meeting Mutation
  const rescheduleMutation = useMutation({
    mutationFn: async ({ meetingId, newStart }: { meetingId: string; newStart: string }) => {
      const startIso = new Date(newStart).toISOString();
      const endIso = new Date(new Date(newStart).getTime() + 30 * 60000).toISOString();
      return apiClient.post(`/responder/meetings/${meetingId}/reschedule`, {
        new_start: startIso,
        new_end: endIso,
      });
    },
    onSuccess: () => {
      setIsRescheduleModalOpen(false);
      setSelectedMeeting(null);
      queryClient.invalidateQueries({ queryKey: ['responder-meetings'] });
      queryClient.invalidateQueries({ queryKey: ['responder-dashboard'] });
    },
  });

  const handleOpenCancel = (m: MeetingItem) => {
    setSelectedMeeting(m);
    setCancelReason('Customer requested cancellation');
    setIsCancelModalOpen(true);
  };

  const handleOpenReschedule = (m: MeetingItem) => {
    setSelectedMeeting(m);
    setNewStartDate(new Date().toISOString().slice(0, 16));
    setIsRescheduleModalOpen(true);
  };

  if (isLoading && !data) {
    return <LoadingState message="Loading Microsoft Outlook & Teams calendar schedule..." />;
  }

  const confirmedCount = bookings.filter((b) => b.status === 'booking_confirmed').length;

  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-900">Discovery Meetings & Calendar</h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              <Video className="w-3.5 h-3.5 mr-1 text-indigo-600" />
              Microsoft Outlook & Teams
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Real-time scheduling orchestration. Double-booking prevention with instant Microsoft Teams online meeting creation.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-xs flex items-center gap-1.5"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            Sync Calendar
          </Button>
        </div>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Confirmed Bookings
            </span>
            <div className="text-2xl font-bold text-slate-900 mt-1">{confirmedCount}</div>
            <div className="text-[11px] text-emerald-600 font-medium mt-1 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              Active on Microsoft Graph
            </div>
          </div>
          <div className="p-3 bg-emerald-50 rounded-xl text-emerald-600">
            <Calendar className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Pending Slot Proposals
            </span>
            <div className="text-2xl font-bold text-slate-900 mt-1">{proposals.length}</div>
            <div className="text-[11px] text-amber-600 font-medium mt-1 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Awaiting Lead Confirmation
            </div>
          </div>
          <div className="p-3 bg-amber-50 rounded-xl text-amber-600">
            <Clock className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Scheduling Policy
            </span>
            <div className="text-xs font-bold text-slate-900 mt-1">24/7 Availability</div>
            <div className="text-[11px] text-slate-500 mt-1">
              Auto-Alternative Slot Finder Active
            </div>
          </div>
          <div className="p-3 bg-indigo-50 rounded-xl text-indigo-600">
            <CalendarDays className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex border-b border-slate-200 text-xs font-semibold text-slate-600 gap-6">
        <button
          onClick={() => setActiveTab('all')}
          className={`pb-2.5 transition-colors border-b-2 ${
            activeTab === 'all'
              ? 'border-indigo-600 text-indigo-700'
              : 'border-transparent hover:text-slate-900'
          }`}
        >
          All Meetings ({bookings.length})
        </button>
        <button
          onClick={() => setActiveTab('confirmed')}
          className={`pb-2.5 transition-colors border-b-2 ${
            activeTab === 'confirmed'
              ? 'border-indigo-600 text-indigo-700'
              : 'border-transparent hover:text-slate-900'
          }`}
        >
          Confirmed Only ({confirmedCount})
        </button>
        <button
          onClick={() => setActiveTab('proposals')}
          className={`pb-2.5 transition-colors border-b-2 ${
            activeTab === 'proposals'
              ? 'border-indigo-600 text-indigo-700'
              : 'border-transparent hover:text-slate-900'
          }`}
        >
          Proposed Alternatives ({proposals.length})
        </button>
      </div>

      {/* Main Content Area */}
      {activeTab !== 'proposals' ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                  <th className="py-3 px-4">Title & Attendee</th>
                  <th className="py-3 px-4">Scheduled Date & Time (UTC)</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Microsoft Teams Link</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {bookings.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400">
                      No calendar meetings found.
                    </td>
                  </tr>
                ) : (
                  bookings
                    .filter((b) => activeTab === 'all' || b.status === 'booking_confirmed')
                    .map((m) => (
                      <tr key={m.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-900">{m.title}</div>
                          <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1.5">
                            <span>{m.attendee_name}</span>
                            <span>•</span>
                            <span>{m.attendee_email}</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-slate-700">
                          {m.start_time}
                        </td>
                        <td className="py-3 px-4">
                          {m.status === 'booking_confirmed' ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                              Confirmed
                            </span>
                          ) : m.status === 'cancelled' ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-100 text-rose-800">
                              Cancelled
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-800">
                              {m.status}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {m.teams_join_url ? (
                            <a
                              href={m.teams_join_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2.5 py-1 rounded border border-indigo-200"
                            >
                              <Video className="w-3.5 h-3.5" />
                              Join Teams Meeting
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          ) : (
                            <span className="text-[11px] text-slate-400">None</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {m.status !== 'cancelled' && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleOpenReschedule(m)}
                                  className="text-xs py-1 px-2"
                                >
                                  Reschedule
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleOpenCancel(m)}
                                  className="text-xs py-1 px-2 text-rose-600 hover:bg-rose-50"
                                >
                                  Cancel
                                </Button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Proposals View */
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6">
          <h2 className="text-sm font-bold text-slate-900 mb-2">Pending Alternative Slot Proposals</h2>
          <p className="text-xs text-slate-500 mb-4">
            Slots automatically searched and offered when a prospect requested an occupied time slot (e.g. 2:00 AM occupied $\rightarrow$ 3:00 AM offered).
          </p>

          <div className="space-y-3">
            {proposals.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-6">No active proposals pending.</p>
            ) : (
              proposals.map((p) => {
                let slots: any[] = [];
                if (Array.isArray(p.offered_slots)) {
                  slots = p.offered_slots;
                } else if (typeof p.offered_slots === 'string') {
                  try {
                    const parsed = JSON.parse(p.offered_slots);
                    slots = Array.isArray(parsed) ? parsed : [];
                  } catch {
                    slots = [];
                  }
                }

                return (
                  <div key={p.id} className="p-4 rounded-lg border border-slate-200 bg-slate-50/50 flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-slate-900">Proposal ID: {p.id}</span>
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-amber-100 text-amber-800">
                          {p.status.toUpperCase()}
                        </span>
                      </div>
                      <div className="mt-2 text-xs text-slate-700">
                        <span className="font-medium text-slate-500">Offered Slots: </span>
                        {slots.map((s: any, i: number) => (
                          <span key={i} className="inline-block mr-2 px-2 py-0.5 bg-white border border-slate-200 rounded font-semibold text-slate-800 text-[11px]">
                            {s.display || s.start}
                          </span>
                        ))}
                      </div>
                      <div className="mt-1 text-[10px] text-slate-400">
                        Expires: {p.expires_at}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Cancel Modal */}
      <Modal
        isOpen={isCancelModalOpen}
        onClose={() => setIsCancelModalOpen(false)}
        title="Cancel Calendar Meeting"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-600">
            Are you sure you want to cancel the scheduled meeting with{' '}
            <span className="font-semibold">{selectedMeeting?.attendee_name}</span>?
            This will update the Outlook Calendar and record the cancellation in the timeline.
          </p>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Cancellation Reason</label>
            <input
              type="text"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button size="sm" variant="outline" onClick={() => setIsCancelModalOpen(false)}>
              Keep Meeting
            </Button>
            <Button
              size="sm"
              onClick={() => {
                if (selectedMeeting) {
                  cancelMutation.mutate({ meetingId: selectedMeeting.id, reason: cancelReason });
                }
              }}
              disabled={cancelMutation.isPending}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {cancelMutation.isPending ? 'Cancelling...' : 'Confirm Cancellation'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Reschedule Modal */}
      <Modal
        isOpen={isRescheduleModalOpen}
        onClose={() => setIsRescheduleModalOpen(false)}
        title="Reschedule Meeting"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-600">
            Pick a new start date and time for discovery meeting with{' '}
            <span className="font-semibold">{selectedMeeting?.attendee_name}</span>.
          </p>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">New Start Time</label>
            <input
              type="datetime-local"
              value={newStartDate}
              onChange={(e) => setNewStartDate(e.target.value)}
              className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button size="sm" variant="outline" onClick={() => setIsRescheduleModalOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => {
                if (selectedMeeting && newStartDate) {
                  rescheduleMutation.mutate({ meetingId: selectedMeeting.id, newStart: newStartDate });
                }
              }}
              disabled={rescheduleMutation.isPending || !newStartDate}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              {rescheduleMutation.isPending ? 'Updating...' : 'Confirm Reschedule'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
