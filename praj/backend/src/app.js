const express = require("express");
const port = 8080;
const app = express();




app.listen(port, (req, res) =>{
    console.log(`server listining on port ${port}`);
    
})