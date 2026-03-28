import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { FileText, Download, FileSpreadsheet, Image as ImageIcon, Calendar, Search, Filter, ArrowLeft, CheckCircle } from 'lucide-react';
import * as XLSX from 'xlsx';
const BASE_URL = 'http://localhost:8080';
import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

export default function CRSReview() {
  const navigate = useNavigate();

  const [metadata, setMetadata]       = useState(null);
  const [allTableData, setAllTableData] = useState([]);
  const [tableData, setTableData]     = useState([]);
  const [engineers, setEngineers]     = useState([]);
  const [rowEdits, setRowEdits]       = useState({});
  const [searchTerm, setSearchTerm]   = useState('');
  const [filterStatus, setFilterStatus] = useState('All');

  const { drawingNo, id: routeId } = useParams();
  const actualDocId = drawingNo || routeId; 

  useEffect(() => {
    if (!actualDocId) return;

    fetch(`${BASE_URL}/api/comments/document/${actualDocId}`, { mode: 'cors' })
      .then(res => { 
        if (!res.ok) throw new Error(`Comments fetch failed: ${res.status}`); 
        return res.json(); 
      })
      .then(data => {
        const commentsArray = Array.isArray(data) ? data : (data.comments || data.data || []);
        const mapped = commentsArray.map((item, index) => {
          
          let formattedTarget = '';
          if (item.target_closure_date) {
            formattedTarget = new Date(item.target_closure_date).toISOString().split('T')[0];
          }

          return {
            sr:    index + 1,
            doc:   item.document_id || actualDocId,
            rev:   '-',
            cDoc:  '-',
            cRev:  '-',
            page:  item.page_sheet,
            cId:   item.comment_id || item.id || `C-${index + 1}`,
            // These are the short keys we must use in handleSave!
            comment:  item.actual_extracted_comment || '-',
            snapshotUrl: item.snapshot_file && item.snapshot_file !== 'NA' 
              ? `${BASE_URL}/${item.snapshot_file}` 
              : null,
            person:   item.name_of_person_commented || 'Unknown',
            date: (item.comment_datetime || item.created_at)
              ? new Date(item.comment_datetime || item.created_at).toLocaleDateString()
              : '-',
            color:    item.comment_color || 'Black',
            client:   item.is_client_comment ? 'Yes' : 'No',
            cat:      item.comment_category || 'General',
            hw:       item.is_handwritten ? 'Yes' : 'No',
            conf:     item.extraction_confidence_percent ? `${item.extraction_confidence_percent}%` : '100%',
            
            assignee: item.assigned_to || '',
            target:   formattedTarget,
            crs:      item.crs_ref || '-',
            status:   item.status || 'Open',
          };
        });
        setAllTableData(mapped);
      })
      .catch(err => console.error('Error fetching comments:', err));

    fetch(`${BASE_URL}/api/documents/${actualDocId}`, { mode: 'cors' })
      .then(res => res.ok ? res.json() : null)
      .then(data => { 
        if (data) {
          setMetadata({
            docNo: data.praj_document_number,
            revision: data.praj_revision_number,
            custDocNo: data.customer_document_number,
            custRevision: data.customer_revision,
            supplier: data.supplier_name,
            po: data.supplier_po_number,
            is_released: data.is_released 
          });
        }
      })
      .catch(err => console.error('Error fetching metadata:', err));

    fetch(`${BASE_URL}/api/engineers`, { mode: 'cors' })
      .then(res => res.ok ? res.json() : [])
      .then(data => {
        let engArray = Array.isArray(data) ? data : (data.engineers || data.data || []);
        if (engArray.length === 0) {
          engArray = [
            { id: 1, name: "Yash R. (Lead)" },
            { id: 2, name: "Suraj P. (Mech)" },
            { id: 3, name: "Amit K. (Elec)" },
            { id: 4, name: "Priya S. (Civil)" }
          ];
        }
        setEngineers(engArray);
      })
      .catch(err => console.error('Error fetching engineers:', err));
  }, [actualDocId]);

  useEffect(() => {
    let filtered = allTableData;
    if (searchTerm.trim()) {
      const lower = searchTerm.toLowerCase();
      filtered = filtered.filter(r =>
        r.comment.toLowerCase().includes(lower) ||
        r.person.toLowerCase().includes(lower) ||
        r.cId.toLowerCase().includes(lower) ||
        r.cat.toLowerCase().includes(lower)
      );
    }
    if (filterStatus !== 'All') filtered = filtered.filter(r => r.status === filterStatus);
    setTableData(filtered);
  }, [searchTerm, filterStatus, allTableData]);

  function setField(rowId, field, value) {
    setRowEdits(prev => ({
      ...prev,
      [rowId]: {
        ...(prev[rowId] || {}),
        [field]: value
      }
    }));
  }

  async function handleRelease() {
    const confirmRelease = window.confirm("Are you sure you want to release this document?");
    if (!confirmRelease) return;

    try {
      const res = await fetch(`${BASE_URL}/api/documents/${actualDocId}/release`, {
        method: 'PUT',
        mode: 'cors'
      });
      
      if (!res.ok) throw new Error('Failed to release document');
      
      setMetadata(prev => ({ ...prev, is_released: true }));
      alert("Document released successfully!");
    } catch (err) {
      console.error('Release failed:', err);
      alert('Failed to release document. Check console for details.');
    }
  }

  async function handleSave(clickedRow) {
    const currentRow = allTableData.find(r => r.cId === clickedRow.cId);
    
    if (!currentRow) {
      alert("Error: Could not find this row in the data table.");
      return;
    }

    const extractedCommentId = currentRow.cId;
    const edits = rowEdits[extractedCommentId] || {};
    
    // ✅ FIX: Mapping from the shortened frontend state keys back to backend schema
    // ✅ FIX: Converting "Yes"/"No" back to "Y"/"N" for Postgres
    const payload = {
      actual_extracted_comment: currentRow.comment === '-' ? "" : currentRow.comment,
      comment_color: currentRow.color,
      comment_category: currentRow.cat,
      is_client_comment: currentRow.client === 'Yes' ? 'Y' : 'N',
      is_handwritten: currentRow.hw === 'Yes' ? 'Y' : 'N',
      assigned_to: edits.assignee ?? currentRow.assignee, 
      target_closure_date: (edits.target ?? currentRow.target) || null,
      status: edits.status ?? currentRow.status
    };

    console.log(`🚀 Sending PUT request to: ${BASE_URL}/api/comments/${extractedCommentId}`);
    console.log("📦 Payload Data:", payload);

    try {
      const res = await fetch(`${BASE_URL}/api/comments/${extractedCommentId}`, {
        method: 'PUT', 
        mode: 'cors',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      if (!res.ok) {
         const errorData = await res.json().catch(() => ({ message: res.statusText }));
         console.error("❌ Backend Error Response:", errorData);
         throw new Error(`Backend Error (${res.status}): ${errorData.message}`);
      }
      
      setAllTableData(prev => prev.map(r => r.cId === extractedCommentId
        ? { 
            ...r, 
            assignee: payload.assigned_to, 
            target: payload.target_closure_date, 
            status: payload.status 
          }
        : r
      ));
      
      setRowEdits(prev => { 
        const newEdits = { ...prev }; 
        delete newEdits[extractedCommentId]; 
        return newEdits; 
      });
      
      alert(`Comment ${extractedCommentId} updated successfully!`);
      
    } catch (err) {
      console.error('Save failed:', err);
      alert(`FAILED TO SAVE:\n\n${err.message}\n\nCheck browser console for more details.`);
    }
  }

// async function handleDownload(format) {
//     if (format === 'pdf') {
//       alert("PDF download still requires the backend. We'll leave that as is for now!");
//       return; 
//     }

//     try {
//       // 1. Map your on-screen data to clean column names for Excel
//       const exportData = tableData.map(row => {
//         // Grab any unsaved edits, otherwise fall back to the original row data
//         const currentAssignee = rowEdits[row.cId]?.assignee ?? row.assignee;
//         const currentTarget = rowEdits[row.cId]?.target ?? row.target;
//         const currentStatus = rowEdits[row.cId]?.status ?? row.status;
//         const currentResolution = rowEdits[row.cId]?.resolution ?? row.res;

//         return {
//           'Sr. No': row.sr,
//           'Doc No': row.doc,
//           'Rev': row.rev,
//           'Cust Doc': row.cDoc,
//           'Cust Rev': row.cRev,
//           'Page': row.page,
//           'Comment ID': row.cId,
//           'Comment': row.comment,
//           // ✅ ADDED: Include the Snapshot URL (or a placeholder if none exists)
//           'Snapshot Link': row.snapshotUrl || 'No Image', 
//           'Person': row.person,
//           'Date': row.date,
//           'Client?': row.client,
//           'Category': row.cat,
//           'Handwritten?': row.hw,
//           'Assigned To': currentAssignee,
//           'Target Date': currentTarget,
//           'CRS Ref': row.crs,
//           'Resolution': currentResolution,
//           'Status': currentStatus,
//           'Evidence': rowEdits[row.cId]?.evidence ?? row.ev
//         };
//       });

//       // 2. Create the Excel workbook and sheet
//       const worksheet = XLSX.utils.json_to_sheet(exportData);
//       const workbook = XLSX.utils.book_new();
      
//       // Name the tab at the bottom of the Excel file
//       XLSX.utils.book_append_sheet(workbook, worksheet, "CRS Comments");

//       // 3. Auto-size columns slightly
//       const columnWidths = [
//         { wch: 8 },  // Sr No
//         { wch: 15 }, // Doc No
//         { wch: 8 },  // Rev
//         { wch: 15 }, // Cust Doc
//         { wch: 8 },  // Cust Rev
//         { wch: 8 },  // Page
//         { wch: 15 }, // Comment ID
//         { wch: 40 }, // Comment
//         { wch: 45 }, // Snapshot Link (✅ ADDED width for the URL)
//         { wch: 15 }, // Person
//         { wch: 12 }, // Date
//         { wch: 10 }, // Client
//         { wch: 15 }, // Category
//         { wch: 12 }, // Handwritten
//         { wch: 15 }, // Assigned To
//         { wch: 12 }, // Target Date
//         { wch: 15 }, // CRS Ref
//         { wch: 30 }, // Resolution
//         { wch: 12 }, // Status
//         { wch: 20 }  // Evidence
//       ];
//       worksheet['!cols'] = columnWidths;

//       // 4. Trigger the download
//       const fileName = `Document-${actualDocId || metadata?.docNo || 'Export'}-crs.xlsx`;
//       XLSX.writeFile(workbook, fileName);

//     } catch (err) {
//       console.error('Excel export failed:', err);
//       alert('Failed to generate the Excel file.');
//     }
//   }


async function handleDownload(format) {
  if (format === 'pdf') {
    alert("PDF download still requires the backend.");
    return;
  }

  try {
    if (!window.ExcelJS) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.4.0/exceljs.min.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
    }

    const workbook = new window.ExcelJS.Workbook();
    workbook.creator  = 'CRS System';
    workbook.created  = new Date();

    /* ─────────────────────────────────────────────────────────────────
       DESIGN TOKENS  (change here to retheme everything)
    ───────────────────────────────────────────────────────────────── */
    const T = {
      navy:       'FF0D1B2A',   // darkest — titles, headers
      navyMid:    'FF1B2D45',   // section headers
      navyLight:  'FF1E3A5F',   // sub-headers
      gold:       'FFC9A84C',   // accent stripe
      goldLight:  'FFFDF3DC',   // accent bg tint
      slate:      'FF4A5568',   // body text
      silver:     'FFE2E8F0',   // alternate row
      white:      'FFFFFFFF',
      offWhite:   'FFF8FAFC',
      divider:    'FFD1DCE8',

      // Status palette
      open:       { bg: 'FFFEE2E2', text: 'FF991B1B', pill: 'FFEF4444' },
      inProgress: { bg: 'FFFEF3C7', text: 'FF92400E', pill: 'FFF59E0B' },
      closed:     { bg: 'FFD1FAE5', text: 'FF065F46', pill: 'FF10B981' },
      other:      { bg: 'FFE0E7FF', text: 'FF3730A3', pill: 'FF6366F1' },
    };

    /* ─────────────────────────────────────────────────────────────────
       UTILITY FUNCTIONS
    ───────────────────────────────────────────────────────────────── */
    const gc  = (ws, r, c) => ws.getCell(r, c);
    const gr  = (ws, r)    => ws.getRow(r);
    const mg  = (ws, r1, c1, r2, c2) => ws.mergeCells(r1, c1, r2, c2);

    function applyCell(ws, r, c, value, {
      bg = T.white, fg = T.navy, bold = false, size = 10,
      align = 'left', vAlign = 'middle', wrap = false,
      borderColor = null, borderStyle = 'thin',
      italic = false, indent = 0, numFmt = null
    } = {}) {
      const cl = gc(ws, r, c);
      cl.value     = value;
      cl.font      = { bold, italic, size, color: { argb: fg }, name: 'Calibri' };
      cl.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg } };
      cl.alignment = { horizontal: align, vertical: vAlign, wrapText: wrap, indent };
      if (numFmt) cl.numFmt = numFmt;
      if (borderColor) {
        const b = { style: borderStyle, color: { argb: borderColor } };
        cl.border = { top: b, bottom: b, left: b, right: b };
      }
      return cl;
    }

    function paintRow(ws, r, fromCol, toCol, bgArgb) {
      for (let c = fromCol; c <= toCol; c++) {
        gc(ws, r, c).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bgArgb } };
      }
    }

    function accentStripe(ws, r, fromCol, toCol) {
      // 2-px gold top border on a white row = elegant section divider
      for (let c = fromCol; c <= toCol; c++) {
        const cl = gc(ws, r, c);
        if (!cl.border) cl.border = {};
        cl.border.top = { style: 'medium', color: { argb: T.gold } };
      }
    }

    /* ─────────────────────────────────────────────────────────────────
       COMPUTE STATISTICS
    ───────────────────────────────────────────────────────────────── */
    const total      = tableData.length;
    const getStatus  = row => (rowEdits[row.cId]?.status ?? row.status ?? '').toLowerCase().trim();
    const open       = tableData.filter(r => getStatus(r) === 'open').length;
    const inProgress = tableData.filter(r => getStatus(r) === 'in progress').length;
    const closed     = tableData.filter(r => getStatus(r) === 'closed').length;
    const other      = total - open - inProgress - closed;
    const pct        = n => total > 0 ? ((n / total) * 100).toFixed(1) : '0.0';

    const catMap = {};
    tableData.forEach(r => { const k = r.cat || 'Uncategorized'; catMap[k] = (catMap[k] || 0) + 1; });
    const catEntries = Object.entries(catMap).sort((a, b) => b[1] - a[1]);

    const assigneeMap = {};
    tableData.forEach(r => {
      const k = rowEdits[r.cId]?.assignee ?? r.assignee ?? 'Unassigned';
      assigneeMap[k] = (assigneeMap[k] || 0) + 1;
    });
    const assigneeEntries = Object.entries(assigneeMap).sort((a, b) => b[1] - a[1]);

    const dateNow = new Date().toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' });

    /* ═════════════════════════════════════════════════════════════════
       SHEET 1 — DASHBOARD
    ═════════════════════════════════════════════════════════════════ */
    const dash = workbook.addWorksheet('Dashboard');
    dash.showGridLines = false;

    // Column widths — 12 columns total (A–L)
    [2,2,16,14,14,14,14,14,14,14,14,2].forEach((w,i) => { dash.getColumn(i+1).width = w; });

    let R = 1; // current row cursor

    /* ── COVER HEADER ─────────────────────────────────────────── */
    // Full navy banner
    for (let r = R; r <= R+5; r++) paintRow(dash, r, 1, 12, T.navy);
    gr(dash, R).height = 6;
    gr(dash, R+1).height = 8;

    // Gold accent line
    for (let c = 1; c <= 12; c++) {
      gc(dash, R+2, c).border = { top: { style: 'thick', color: { argb: T.gold } } };
    }

    mg(dash, R+2, 3, R+2, 11);
    applyCell(dash, R+2, 3, 'CRS COMMENT REVIEW SYSTEM', {
      bg: T.navy, fg: T.gold, bold: true, size: 20, align: 'left', vAlign: 'bottom'
    });
    gr(dash, R+2).height = 36;

    mg(dash, R+3, 3, R+3, 11);
    applyCell(dash, R+3, 3, `Statistical Dashboard  ·  ${metadata?.docNo || 'Document Export'}  ·  Generated ${dateNow}`, {
      bg: T.navy, fg: 'FFAABDD1', bold: false, size: 11, align: 'left'
    });
    gr(dash, R+3).height = 22;

    gr(dash, R+4).height = 8;
    paintRow(dash, R+4, 1, 12, T.navy);
    gr(dash, R+5).height = 16;
    paintRow(dash, R+5, 1, 12, T.offWhite);

    R = R + 6;

    /* ── KPI CARDS ────────────────────────────────────────────── */
    // Section label
    mg(dash, R, 3, R, 11);
    applyCell(dash, R, 3, 'EXECUTIVE SUMMARY', {
      bg: T.offWhite, fg: T.navyLight, bold: true, size: 9, align: 'left', italic: false
    });
    gr(dash, R).height = 18;
    paintRow(dash, R, 1, 2, T.offWhite);
    paintRow(dash, R, 12, 12, T.offWhite);
    R++;

    const kpis = [
      { label: 'TOTAL COMMENTS', value: total,      sub: '100%',      ...T, bg: T.navyLight,   fg: T.white,  subFg: T.gold      },
      { label: 'OPEN',           value: open,        sub: `${pct(open)}%`,       bg: T.open.bg,       fg: T.open.text,  subFg: T.open.pill      },
      { label: 'IN PROGRESS',    value: inProgress,  sub: `${pct(inProgress)}%`, bg: T.inProgress.bg, fg: T.inProgress.text, subFg: T.inProgress.pill },
      { label: 'CLOSED',         value: closed,      sub: `${pct(closed)}%`,     bg: T.closed.bg,     fg: T.closed.text, subFg: T.closed.pill    },
      { label: 'OTHER',          value: other,       sub: `${pct(other)}%`,      bg: T.other.bg,      fg: T.other.text,  subFg: T.other.pill     },
    ];

    // Card layout: each card = cols 3–4, 4–5, 5–6 … spread across 5 cols (3,4,5,6,7 → pairs)
    const cardCols = [3, 5, 7, 9, 11]; // left col of each card (each card = 1 col wide, merged 2 rows)

    gr(dash, R).height     = 44;
    gr(dash, R+1).height   = 20;
    gr(dash, R+2).height   = 10;
    paintRow(dash, R,   1, 12, T.offWhite);
    paintRow(dash, R+1, 1, 12, T.offWhite);
    paintRow(dash, R+2, 1, 12, T.offWhite);

    kpis.forEach((kpi, i) => {
      const col = cardCols[i];

      mg(dash, R, col, R, col + 1);
      applyCell(dash, R, col, kpi.value, {
        bg: kpi.bg, fg: kpi.fg, bold: true, size: 28, align: 'center', vAlign: 'bottom'
      });

      mg(dash, R+1, col, R+1, col+1);
      applyCell(dash, R+1, col, kpi.label, {
        bg: kpi.bg, fg: kpi.fg, bold: true, size: 8, align: 'center', vAlign: 'top'
      });
    });

    R += 3;

    /* ── STATUS DISTRIBUTION (horizontal bar) ─────────────────── */
    gr(dash, R).height = 20;
    paintRow(dash, R, 1, 12, T.offWhite);
    R++;

    // Section header strip
    for (let c = 1; c <= 12; c++) paintRow(dash, R, c, c, T.navyMid);
    mg(dash, R, 3, R, 11);
    applyCell(dash, R, 3, 'STATUS DISTRIBUTION', {
      bg: T.navyMid, fg: T.white, bold: true, size: 11, align: 'left'
    });
    // gold left border on section header
    gc(dash, R, 3).border = { left: { style: 'thick', color: { argb: T.gold } } };
    gr(dash, R).height = 26;
    R++;
    gr(dash, R).height = 8; paintRow(dash, R, 1, 12, T.offWhite); R++;

    const bars = [
      { label: 'Open',        count: open,        ...T.open        },
      { label: 'In Progress', count: inProgress,  ...T.inProgress  },
      { label: 'Closed',      count: closed,      ...T.closed      },
      { label: 'Other',       count: other,       ...T.other       },
    ];

    bars.forEach(bar => {
      paintRow(dash, R, 1, 12, T.offWhite);
      gr(dash, R).height = 24;

      // Label
      applyCell(dash, R, 3, bar.label, {
        bg: T.offWhite, fg: T.slate, bold: true, size: 10, align: 'right', vAlign: 'middle'
      });

      // Bar track: cols 4–10 (7 cols)
      const TOTAL_UNITS = 7;
      const filled = total > 0 ? Math.round((bar.count / total) * TOTAL_UNITS) : 0;
      for (let col = 4; col <= 10; col++) {
        const isFilled = col - 4 < filled;
        gc(dash, R, col).fill = {
          type: 'pattern', pattern: 'solid',
          fgColor: { argb: isFilled ? bar.pill : 'FFE2E8F0' }
        };
        // thin divider between bar cells
        gc(dash, R, col).border = {
          left:  { style: 'thin', color: { argb: T.white } },
          right: { style: 'thin', color: { argb: T.white } },
        };
      }

      // Value + pct label
      applyCell(dash, R, 11, `${bar.count}  (${pct(bar.count)}%)`, {
        bg: T.offWhite, fg: bar.text, bold: true, size: 10, align: 'left', vAlign: 'middle'
      });

      R++;
      gr(dash, R).height = 4; paintRow(dash, R, 1, 12, T.offWhite); R++;
    });

    gr(dash, R).height = 16; paintRow(dash, R, 1, 12, T.offWhite); R++;

    /* ── BREAKDOWN TABLES (side by side) ─────────────────────── */
    // Section header
    for (let c = 1; c <= 12; c++) paintRow(dash, R, c, c, T.navyMid);
    mg(dash, R, 3, R, 6);
    applyCell(dash, R, 3, 'BY CATEGORY', {
      bg: T.navyMid, fg: T.white, bold: true, size: 11, align: 'left'
    });
    gc(dash, R, 3).border = { left: { style: 'thick', color: { argb: T.gold } } };

    mg(dash, R, 8, R, 11);
    applyCell(dash, R, 8, 'BY ASSIGNEE', {
      bg: T.navyMid, fg: T.white, bold: true, size: 11, align: 'left'
    });
    gc(dash, R, 8).border = { left: { style: 'thick', color: { argb: T.gold } } };
    gr(dash, R).height = 26; R++;

    // Sub-header row
    paintRow(dash, R, 1, 12, T.silver);
    gr(dash, R).height = 18;
    applyCell(dash, R, 3, 'Category',     { bg: T.silver, fg: T.navyLight, bold: true, size: 9 });
    applyCell(dash, R, 5, 'Count',        { bg: T.silver, fg: T.navyLight, bold: true, size: 9, align: 'center' });
    applyCell(dash, R, 6, 'Share',        { bg: T.silver, fg: T.navyLight, bold: true, size: 9, align: 'center' });
    applyCell(dash, R, 8, 'Assignee',     { bg: T.silver, fg: T.navyLight, bold: true, size: 9 });
    applyCell(dash, R, 10, 'Count',       { bg: T.silver, fg: T.navyLight, bold: true, size: 9, align: 'center' });
    applyCell(dash, R, 11, 'Share',       { bg: T.silver, fg: T.navyLight, bold: true, size: 9, align: 'center' });
    R++;

    const maxRows = Math.max(catEntries.length, assigneeEntries.length);
    for (let i = 0; i < maxRows; i++) {
      const rowBg  = i % 2 === 0 ? T.white : T.offWhite;
      paintRow(dash, R, 1, 12, rowBg);
      gr(dash, R).height = 17;

      // Category side
      if (catEntries[i]) {
        const [cat, cnt] = catEntries[i];
        applyCell(dash, R, 3, cat,                   { bg: rowBg, fg: T.slate,     size: 10, align: 'left' });
        applyCell(dash, R, 5, cnt,                   { bg: rowBg, fg: T.navyLight, size: 10, bold: true, align: 'center' });
        applyCell(dash, R, 6, `${pct(cnt)}%`,        { bg: rowBg, fg: T.slate,     size: 10, align: 'center' });
      }
      // Divider gap col 7 stays bg
      gc(dash, R, 7).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: T.silver } };

      // Assignee side
      if (assigneeEntries[i]) {
        const [name, cnt] = assigneeEntries[i];
        applyCell(dash, R, 8,  name,          { bg: rowBg, fg: T.slate,     size: 10, align: 'left' });
        applyCell(dash, R, 10, cnt,            { bg: rowBg, fg: T.navyLight, size: 10, bold: true, align: 'center' });
        applyCell(dash, R, 11, `${pct(cnt)}%`, { bg: rowBg, fg: T.slate,     size: 10, align: 'center' });
      }

      // Bottom border on each data row
      for (let c = 3; c <= 11; c++) {
        if (!gc(dash, R, c).border) gc(dash, R, c).border = {};
        gc(dash, R, c).border.bottom = { style: 'hair', color: { argb: T.divider } };
      }

      R++;
    }

    // Footer bar
    gr(dash, R).height = 20;
    for (let c = 1; c <= 12; c++) paintRow(dash, R, c, c, T.navy);
    mg(dash, R, 3, R, 11);
    applyCell(dash, R, 3, `Confidential  ·  ${metadata?.docNo || ''}  ·  ${dateNow}`, {
      bg: T.navy, fg: 'FF6B8CAE', size: 8, italic: true, align: 'center'
    });
    R++;

    /* ═════════════════════════════════════════════════════════════════
       SHEET 2 — DATA TABLE
    ═════════════════════════════════════════════════════════════════ */
    const ws = workbook.addWorksheet('Comment Register');
    ws.showGridLines = false;

    const cols = [
      { header: 'Sr.',          key: 'sr',         width: 6  },
      { header: 'Doc No.',      key: 'doc',        width: 16 },
      { header: 'Rev',          key: 'rev',        width: 7  },
      { header: 'Cust Doc',     key: 'cDoc',       width: 15 },
      { header: 'Cust Rev',     key: 'cRev',       width: 8  },
      { header: 'Page',         key: 'page',       width: 7  },
      { header: 'Comment ID',   key: 'cId',        width: 14 },
      { header: 'Comment',      key: 'comment',    width: 42 },
      { header: 'Snapshot',     key: 'snapshot',   width: 22 },
      { header: 'Person',       key: 'person',     width: 14 },
      { header: 'Date',         key: 'date',       width: 12 },
      { header: 'Client?',      key: 'client',     width: 9  },
      { header: 'Category',     key: 'cat',        width: 14 },
      { header: 'Handwritten?', key: 'hw',         width: 12 },
      { header: 'Assigned To',  key: 'assignee',   width: 15 },
      { header: 'Target Date',  key: 'target',     width: 12 },
      { header: 'CRS Ref',      key: 'crs',        width: 13 },
      { header: 'Resolution',   key: 'resolution', width: 32 },
      { header: 'Status',       key: 'status',     width: 13 },
      { header: 'Evidence',     key: 'evidence',   width: 18 },
    ];
    ws.columns = cols;

    // Freeze pane + view
    ws.views = [{ state: 'frozen', ySplit: 3 }];

    // Top banner (2 rows)
    for (let r = 1; r <= 2; r++) paintRow(ws, r, 1, cols.length, T.navy);
    mg(ws, 1, 1, 1, cols.length);
    applyCell(ws, 1, 1, 'CRS COMMENT REGISTER', {
      bg: T.navy, fg: T.gold, bold: true, size: 14, align: 'left', vAlign: 'bottom'
    });
    gc(ws, 1, 1).border = { bottom: { style: 'medium', color: { argb: T.gold } } };
    gr(ws, 1).height = 30;

    mg(ws, 2, 1, 2, cols.length);
    applyCell(ws, 2, 1, `${metadata?.docNo || 'Document Export'}  ·  ${total} comments  ·  Generated ${dateNow}`, {
      bg: T.navy, fg: 'FFAABDD1', size: 9, italic: true, align: 'left'
    });
    gr(ws, 2).height = 16;

    // Column header row (row 3)
    gr(ws, 3).height = 22;
    cols.forEach((col, i) => {
      const c = i + 1;
      applyCell(ws, 3, c, col.header, {
        bg: T.navyLight, fg: T.white, bold: true, size: 9,
        align: 'center', vAlign: 'middle'
      });
      gc(ws, 3, c).border = {
        bottom: { style: 'medium', color: { argb: T.gold } },
        right:  c < cols.length ? { style: 'thin', color: { argb: 'FF2A4A6B' } } : undefined,
      };
    });

    // Helper: resolve status colors
    function statusTokens(status) {
      const s = (status || '').toLowerCase().trim();
      if (s === 'open')        return T.open;
      if (s === 'in progress') return T.inProgress;
      if (s === 'closed')      return T.closed;
      return T.other;
    }

    async function fetchImageAsBase64(url) {
      if (!url) return null;
      try {
        const fetchUrl = url.startsWith('http://localhost:8080/output')
          ? url
          : `http://localhost:8080/api/image-proxy?url=${encodeURIComponent(url)}`;
        const res  = await fetch(fetchUrl);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const ext  = blob.type?.includes('jpeg') ? 'jpeg' : blob.type?.includes('gif') ? 'gif' : 'png';
        const base64 = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result.split(',')[1]);
          reader.onerror  = reject;
          reader.readAsDataURL(blob);
        });
        return { base64, extension: ext };
      } catch {
        return null;
      }
    }

    const IMAGE_COL = 9;

    for (let i = 0; i < tableData.length; i++) {
      const row    = tableData[i];
      const excelR = i + 4; // rows 1-3 are banner + header

      const currentAssignee   = rowEdits[row.cId]?.assignee   ?? row.assignee;
      const currentTarget     = rowEdits[row.cId]?.target     ?? row.target;
      const currentStatus     = rowEdits[row.cId]?.status     ?? row.status;
      const currentResolution = rowEdits[row.cId]?.resolution ?? row.res;

      const tok = statusTokens(currentStatus);
      const rowBg = i % 2 === 0 ? T.white : T.offWhite;

      ws.addRow({
        sr: row.sr, doc: row.doc, rev: row.rev, cDoc: row.cDoc, cRev: row.cRev,
        page: row.page, cId: row.cId, comment: row.comment, snapshot: '',
        person: row.person, date: row.date, client: row.client, cat: row.cat,
        hw: row.hw, assignee: currentAssignee, target: currentTarget,
        crs: row.crs, resolution: currentResolution,
        status: currentStatus,
        evidence: rowEdits[row.cId]?.evidence ?? row.ev,
      });

      gr(ws, excelR).height = 58;

      // Style every cell in this row
      cols.forEach((col, ci) => {
        const c  = ci + 1;
        const cl = gc(ws, excelR, c);

        // Status column gets a coloured pill treatment
        if (col.key === 'status') {
          cl.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: tok.bg } };
          cl.font      = { bold: true, size: 9, color: { argb: tok.text }, name: 'Calibri' };
          cl.alignment = { horizontal: 'center', vertical: 'middle' };
          cl.border    = {
            top:    { style: 'thin', color: { argb: tok.pill } },
            bottom: { style: 'thin', color: { argb: tok.pill } },
            left:   { style: 'thin', color: { argb: tok.pill } },
            right:  { style: 'thin', color: { argb: tok.pill } },
          };
        } else {
          cl.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: rowBg } };
          cl.font      = { size: 9, color: { argb: T.slate }, name: 'Calibri' };
          cl.alignment = { vertical: 'middle', wrapText: col.key === 'comment' || col.key === 'resolution' };
          cl.border    = {
            bottom: { style: 'hair', color: { argb: T.divider } },
            right:  c < cols.length
              ? { style: 'hair', color: { argb: T.divider } }
              : undefined,
          };
        }
      });

      // Embed snapshot image
      if (row.snapshotUrl) {
        const imgData = await fetchImageAsBase64(row.snapshotUrl);
        if (imgData) {
          const imageId = workbook.addImage({ base64: imgData.base64, extension: imgData.extension });
          ws.addImage(imageId, {
            tl: { col: IMAGE_COL - 1, row: excelR - 1 },
            br: { col: IMAGE_COL,     row: excelR     },
            editAs: 'oneCell',
          });
        } else {
          gc(ws, excelR, IMAGE_COL).value = row.snapshotUrl;
        }
      }
    }

    /* ── Download ──────────────────────────────────────────────── */
    const buffer = await workbook.xlsx.writeBuffer();
    const blob   = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    });
    const dlUrl  = URL.createObjectURL(blob);
    const a      = document.createElement('a');
    a.href       = dlUrl;
    a.download   = `CRS-${actualDocId || metadata?.docNo || 'Export'}-${new Date().toISOString().slice(0,10)}.xlsx`;
    a.click();
    URL.revokeObjectURL(dlUrl);

  } catch (err) {
    console.error('Excel export failed:', err);
    alert('Failed to generate the Excel file.');
  }
}




  const getCategoryColor = (cat) => {
    switch (cat?.toLowerCase()) {
      case 'safety':      return 'text-red-600 bg-red-50 border-red-100';
      case 'design':      return 'text-blue-600 bg-blue-50 border-blue-100';
      case 'maintenance': return 'text-emerald-600 bg-emerald-50 border-emerald-100';
      case 'labeling':    return 'text-amber-600 bg-amber-50 border-amber-100';
      case 'specs':       return 'text-teal-600 bg-teal-50 border-teal-100';
      case 'technical':   return 'text-indigo-600 bg-indigo-50 border-indigo-100';
      default:            return 'text-slate-600 bg-slate-50 border-slate-100';
    }
  };

  return (
    <Layout>
      <div className="max-w-full 2xl:max-w-7xl mx-auto space-y-6">

        {/* ── Header ── */}
        <div className="flex justify-between items-end">
          <div>
            <button
              onClick={() => navigate('/crs-lookup')}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-2 transition-colors"
            >
              <ArrowLeft size={13} /> Back to CRS Lookup
            </button>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-800">CRS Review — {actualDocId || metadata?.docNo}</h1>
              {metadata?.is_released && (
                <span className="bg-emerald-100 text-emerald-700 text-xs px-2.5 py-1 rounded-md font-bold uppercase tracking-wide border border-emerald-200">
                  Released
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-0.5">Inline comment resolution — assign and update status</p>
          </div>
          
          <div className="flex gap-3">
            {metadata && !metadata.is_released && (
              <button 
                onClick={handleRelease}
                className="bg-white border border-slate-200 hover:bg-emerald-50 hover:border-emerald-200 text-emerald-600 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm"
              >
                <CheckCircle size={16} /> Release Document
              </button>
            )}

            <button onClick={() => handleDownload('excel')}
              className="bg-white border border-slate-200 hover:bg-slate-50 text-indigo-600 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm">
              <FileSpreadsheet size={16} className="text-emerald-500" /> Download Excel
            </button>
            {/* <button onClick={() => handleDownload('pdf')}
              className="bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-sm">
              <FileText size={16} /> Download PDF
            </button> */}
          </div>
        </div>

        {/* ── Metadata Banner ── */}
        {metadata && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 grid grid-cols-6 gap-4">
            {[
              { label: 'DOC NO',        val: metadata.docNo        },
              { label: 'REVISION',      val: metadata.revision     },
              { label: 'CUST DOC NO',   val: metadata.custDocNo    },
              { label: 'CUST REVISION', val: metadata.custRevision },
              { label: 'SUPPLIER',      val: metadata.supplier     },
              { label: 'PO',            val: metadata.po           },
            ].map((item, i) => (
              <div key={i}>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">{item.label}</p>
                <p className="font-bold text-slate-800 text-sm">{item.val || '-'}</p>
              </div>
            ))}
          </div>
        )}

        {/* ── Resolution Grid ── */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">

          <div className="p-4 border-b border-slate-100 flex flex-wrap items-center justify-between bg-slate-50/50 gap-4">
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-rose-400" />
              <h3 className="font-bold text-slate-800">Resolution Grid</h3>
              <span className="bg-indigo-100 text-indigo-700 text-[10px] px-2.5 py-0.5 rounded-full font-bold">{tableData.length} comments</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input type="text" placeholder="Search comments..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                  className="pl-8 pr-4 py-1.5 border border-slate-200 rounded-md text-sm outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow w-64" />
              </div>
              <div className="relative">
                <Filter size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
                  className="pl-8 pr-4 py-1.5 border border-slate-200 rounded-md text-sm outline-none focus:ring-2 focus:ring-indigo-500 appearance-none bg-white cursor-pointer">
                  <option value="All">All Statuses</option>
                  <option value="Open">Open</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Closed">Closed</option>
                </select>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[1500px]">
              <thead>
                <tr className="text-[11px] text-slate-400 border-b border-slate-200/60 uppercase tracking-wider bg-white">
                  <th className="p-4 font-bold">Sr.</th>
                  <th className="p-4 font-bold">Doc No</th>
                  <th className="p-4 font-bold">Rev</th>
                  <th className="p-4 font-bold">Cust Doc</th>
                  <th className="p-4 font-bold">Cust Rev</th>
                  <th className="p-4 font-bold">Page</th>
                  <th className="p-4 font-bold">Comment ID</th>
                  <th className="p-4 font-bold min-w-[150px]">Comment</th>
                  <th className="p-4 font-bold">Snapshot</th>
                  <th className="p-4 font-bold">Person</th>
                  <th className="p-4 font-bold">Date</th>
                  <th className="p-4 font-bold">Color</th>
                  <th className="p-4 font-bold">Client?</th>
                  <th className="p-4 font-bold">Category</th>
                  <th className="p-4 font-bold">Handwritten?</th>
                  <th className="p-4 font-bold">Conf %</th>
                  <th className="p-4 font-bold">Assigned To</th>
                  <th className="p-4 font-bold">Target Date</th>
                  <th className="p-4 font-bold">CRS Ref</th>
                  <th className="p-4 font-bold">Status</th>
                  <th className="p-4 font-bold text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="text-sm text-slate-600">
                {tableData.length === 0 ? (
                  <tr><td colSpan={21} className="p-8 text-center text-slate-400 text-sm">No comments match your filter.</td></tr>
                ) : tableData.map((row) => {
                  const edits = rowEdits[row.cId] || {};
                  return (
                    <tr key={row.cId} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="p-4 text-slate-500">{row.sr}</td>
                      <td className="p-4 font-bold text-red-500">{row.doc}</td>
                      <td className="p-4">{row.rev}</td>
                      <td className="p-4 font-bold text-red-500">{row.cDoc}</td>
                      <td className="p-4">{row.cRev}</td>
                      <td className="p-4">{row.page}</td>
                      <td className="p-4 font-bold text-indigo-600">{row.cId}</td>
                      <td className="p-4 font-medium text-slate-800">{row.comment}</td>
                      <td className="p-4 text-center">
                        {row.snapshotUrl
                          ? <a href={row.snapshotUrl} target="_blank" rel="noopener noreferrer"><ImageIcon size={18} className="text-emerald-500/80 mx-auto" /></a>
                          : <ImageIcon size={18} className="text-slate-300 mx-auto" />}
                      </td>
                      <td className="p-4">{row.person}</td>
                      <td className="p-4 text-emerald-600 font-medium">{row.date}</td>
                      <td className="p-4 font-medium" style={{ color: row.color?.toLowerCase() }}>{row.color}</td>
                      <td className="p-4 font-bold text-emerald-600">{row.client}</td>
                      <td className="p-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold border ${getCategoryColor(row.cat)}`}>
                          <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70"></span>
                          {row.cat}
                        </span>
                      </td>
                      <td className="p-4 text-center font-medium">{row.hw}</td>
                      <td className="p-4 font-bold text-emerald-600">{row.conf}</td>

                      <td className="p-4">
                        <select 
                          value={edits.assignee ?? row.assignee} 
                          onChange={e => setField(row.cId, 'assignee', e.target.value)}
                          className="w-full bg-white border border-slate-300 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none">
                          <option value="">Select...</option>
                          {engineers.map(eng => <option key={eng.id} value={eng.name}>{eng.name}</option>)}
                        </select>
                      </td>
                      
                      <td className="p-4">
                        <input 
                          type="date" 
                          value={edits.target ?? row.target ?? ''} 
                          onChange={e => setField(row.cId, 'target', e.target.value)}
                          className="w-[120px] bg-white border border-slate-300 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none" />
                      </td>
                      
                      <td className="p-4 font-bold text-indigo-600">{row.crs}</td>
                      
                      <td className="p-4">
                        <select 
                          value={edits.status ?? row.status} 
                          onChange={e => setField(row.cId, 'status', e.target.value)}
                          className="w-full bg-white border border-slate-300 text-slate-700 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none">
                          <option>Open</option>
                          <option>In Progress</option>
                          <option>Closed</option>
                        </select>
                      </td>
                      
                      <td className="p-4 text-center">
                        <button 
                          onClick={() => handleSave(row)}
                          className="bg-indigo-500 hover:bg-indigo-600 text-white px-3 py-1.5 rounded text-xs font-bold transition-colors shadow-sm">
                          Save
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="p-4 border-t border-slate-200/60 flex justify-between items-center text-sm text-slate-500 bg-white">
            <span>Showing {tableData.length} of {allTableData.length} total comments</span>
            <div className="flex gap-1">
              <button className="w-8 h-8 flex items-center justify-center rounded-md bg-indigo-500 text-white font-bold shadow-sm">1</button>
            </div>
          </div>
        </div>

      </div>
    </Layout>
  );
}