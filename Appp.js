// ---
// jupyter:
//   jupytext:
//     text_representation:
//       extension: .js
//       format_name: percent
//       format_version: '1.3'
//       jupytext_version: 1.17.3
//   kernelspec:
//     display_name: Python (Color_Palette_Env)
//     language: python
//     name: palette_env
// ---

// %%
const { MongoClient } = require("mongodb");

const MONGO_URI = process.env.MONGO_URI || "mongodb://localhost:27017/";
const DB_NAME = process.env.MONGO_DB_NAME || "color_palette_db";

let client;
let db;

let usersCollection;
let likesCollection;
let dislikesCollection;
let palettesCollection;

async function connectDB() {
    try {
        client = new MongoClient(MONGO_URI, {
            serverSelectionTimeoutMS: 3000
        });

        await client.connect();

        // Force connection check
        await client.db("admin").command({ ping: 1 });

        db = client.db(DB_NAME);

        usersCollection = db.collection("users");
        likesCollection = db.collection("likes");
        dislikesCollection = db.collection("dislikes");
        palettesCollection = db.collection("palettes");

        // Create indexes
        await usersCollection.createIndex({ email: 1 }, { unique: true });

        await likesCollection.createIndex(
            { user_id: 1, palette_hash: 1 },
            { unique: true }
        );

        await dislikesCollection.createIndex(
            { user_id: 1, palette_hash: 1 },
            { unique: true }
        );

        await palettesCollection.createIndex({ created_at: 1 });

        console.log("✅ MongoDB Connected Successfully");

    } catch (error) {
        console.error("❌ MongoDB Connection Failed:", error);

        usersCollection = null;
        likesCollection = null;
        dislikesCollection = null;
        palettesCollection = null;
    }
}

module.exports = {
    connectDB,
    getDB: () => db,
    collections: () => ({
        usersCollection,
        likesCollection,
        dislikesCollection,
        palettesCollection
    })
};
