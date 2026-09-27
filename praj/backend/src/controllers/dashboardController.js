const pool = require('../../db/db');

// 1. Get Top Level Stats (Cards)
module.exports.getStats = async (req, res) => {
    try {
        // Run aggregations in parallel
        const [drawingsRes, commentsRes, pendingRes, overdueRes] = await Promise.all([
            pool.query('SELECT COUNT(*) as count FROM documents'),
            pool.query('SELECT COUNT(*) as count FROM comments'),
            pool.query(`SELECT COUNT(*) as count FROM comments WHERE status IN ('Open', 'In Progress')`),
            // Assuming you have a target_closure_date column
            pool.query(`SELECT COUNT(*) as count FROM comments WHERE target_closure_date < CURRENT_DATE AND status != 'Closed'`)
        ]);

        res.json({
            totalDrawings: parseInt(drawingsRes.rows[0].count),
            totalDrawingsTrend: "+5% this week", // Add real logic here later if needed
            commentsExtracted: parseInt(commentsRes.rows[0].count),
            commentsExtractedTrend: "+12% this month",
            pendingReviews: parseInt(pendingRes.rows[0].count),
            pendingReviewsTrend: "-2% from yesterday",
            overdueItems: parseInt(overdueRes.rows[0].count),
            overdueItemsTrend: "Needs immediate action"
        });
    } catch (err) {
        console.error('Error fetching dashboard stats:', err);
        res.status(500).json({ message: 'Server error fetching stats' });
    }
};


// 2. Get CRS Status (Donut Chart)
module.exports.getCrsStatus = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT status, COUNT(*) as count 
            FROM comments 
            GROUP BY status
        `);

        // Initialize default counts
        let counts = { open: 0, inProgress: 0, closed: 0 };
        let total = 0;

        // Map database results to our object
        result.rows.forEach(row => {
            const statusStr = row.status ? row.status.toLowerCase() : 'open';
            const count = parseInt(row.count);
            
            if (statusStr.includes('open')) counts.open += count;
            else if (statusStr.includes('progress')) counts.inProgress += count;
            else if (statusStr.includes('closed')) counts.closed += count;
            
            total += count;
        });

        res.json({
            total: total,
            open: counts.open,
            inProgress: counts.inProgress,
            closed: counts.closed
        });
    } catch (err) {
        console.error('Error fetching CRS status:', err);
        res.status(500).json({ message: 'Server error fetching CRS status' });
    }
};


// 3. Get Comments by Category (Progress Bars)
module.exports.getCategories = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT comment_category as label, COUNT(*) as value 
            FROM comments 
            WHERE comment_category IS NOT NULL 
            GROUP BY comment_category 
            ORDER BY value DESC
        `);

        const rows = result.rows;
        if (rows.length === 0) return res.json([]);

        // Find max value to calculate percentage width for the frontend bars
        const maxVal = Math.max(...rows.map(r => parseInt(r.value)));
        
        // Beautiful Tailwind colors for the categories
        const colors = ['bg-indigo-500', 'bg-emerald-500', 'bg-amber-500', 'bg-rose-500', 'bg-cyan-500', 'bg-purple-500'];

        const categories = rows.map((row, index) => {
            const val = parseInt(row.value);
            return {
                label: row.label,
                value: val,
                percentage: Math.round((val / maxVal) * 100), // Gives a % relative to the highest category
                color: colors[index % colors.length]
            };
        });

        res.json(categories);
    } catch (err) {
        console.error('Error fetching categories:', err);
        res.status(500).json({ message: 'Server error fetching categories' });
    }
};


// 4. Get Engineer Workload (Bar Chart)
module.exports.getEngineerWorkload = async (req, res) => {
    try {
        // NOTE: If assigned_to is just an ID, you might need to JOIN with your users/engineers table
        // Example with JOIN: 
        // SELECT u.name, COUNT(c.id) as count FROM comments c JOIN users u ON c.assigned_to = u.id ...
        
        const result = await pool.query(`
            SELECT assigned_to as name, COUNT(*) as count 
            FROM comments 
            WHERE assigned_to IS NOT NULL AND status != 'Closed'
            GROUP BY assigned_to 
            ORDER BY count DESC 
            LIMIT 6
        `);

        // Handle case where assigned_to might be a raw number in the DB without a name yet
        const engineers = result.rows.map(row => ({
            name: row.name, // Will just output the ID if it's not joined to a name
            count: parseInt(row.count)
        }));

        res.json(engineers);
    } catch (err) {
        console.error('Error fetching engineer workload:', err);
        res.status(500).json({ message: 'Server error fetching engineer workload' });
    }
};


// 5. Get Trends (Area Chart - Last 7 Days)
module.exports.getTrends = async (req, res) => {
    try {
        // Generates the last 7 days dynamically so the graph never breaks
        // If your timestamp column is named differently, change date_of_comment below
        const result = await pool.query(`
            WITH last_7_days AS (
                SELECT generate_series(CURRENT_DATE - INTERVAL '6 days', CURRENT_DATE, '1 day')::date AS date
            )
            SELECT 
                to_char(d.date, 'Mon DD') as date_label,
                COUNT(c.id) as extracted,
                COUNT(c.id) FILTER (WHERE c.status = 'Closed') as resolved
            FROM last_7_days d
            LEFT JOIN comments c ON c.date_of_comment::date = d.date
            GROUP BY d.date
            ORDER BY d.date ASC;
        `);

        const trends = result.rows.map(row => ({
            date: row.date_label,
            extracted: parseInt(row.extracted),
            resolved: parseInt(row.resolved)
        }));

        res.json(trends);
    } catch (err) {
        console.error('Error fetching trends:', err);
        res.status(500).json({ message: 'Server error fetching trends' });
    }
};