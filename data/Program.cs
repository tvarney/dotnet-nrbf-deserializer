using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.Serialization.Formatters.Binary;

namespace TestData
{
    [Serializable]
    public class Primitives
    {
        public bool bool_v;
        public byte byte_v;
        public sbyte sbyte_v;
        public short short_v;
        public ushort ushort_v;
        public int int_v;
        public uint uint_v;
        public long long_v;
        public ulong ulong_v;
        public float float_v;
        public double double_v;
        public decimal decimal_v;
        public DateTime datetime_v;
        public TimeSpan timespan_v;

        public Primitives(int seed) {
            DateTime d1 = new DateTime(1010101010 + seed, DateTimeKind.Local);
            DateTime d2 = new DateTime(685940000 + seed, DateTimeKind.Local);
            TimeSpan interval = d1 - d2;

            bool_v = true;
            byte_v = (byte)75;
            sbyte_v = (sbyte)-39;
            short_v = (short)-30754;
            ushort_v = (ushort)61937;
            int_v = -2019964829;
            uint_v =  4082738291;
            long_v = -9122372936854775843L;
            ulong_v =  17446744973709521615ul;
            float_v = 745.01f;
            double_v = 829.0192;
            decimal_v = 4310865659943.575646355933126m;
            timespan_v = d1 - d2;
            datetime_v = d1;
        }
    }

    [Serializable]
    public class PrimitiveArrays
    {
        public bool[] bools;
        public byte[] bytes;
        public sbyte[] sbytes;
        public short[] shorts;
        public ushort[] ushorts;
        public int[] ints;
        public uint[] uints;
        public long[] longs;
        public ulong[] ulongs;
        public float[] floats;
        public double[] doubles;
        public decimal[] decimals;
        public DateTime[] datetimes;
        public TimeSpan[] timespans;

        public PrimitiveArrays(int size) {
            bools = new bool[size];
            bytes = new byte[size];
            sbytes = new sbyte[size];
            shorts = new short[size];
            ushorts = new ushort[size];
            ints = new int[size];
            uints = new uint[size];
            longs = new long[size];
            ulongs = new ulong[size];
            floats = new float[size];
            doubles = new double[size];
            decimals = new decimal[size];
            datetimes = new DateTime[size];
            timespans = new TimeSpan[size];

            DateTime reference = new DateTime(1000010, DateTimeKind.Local);
            for(int i = 0; i < size; ++i) {
                bools[i] = (i%2) == 0;
                bytes[i] = (byte)i;
                sbytes[i] = (sbyte)i;
                shorts[i] = (short)i;
                ushorts[i] = (ushort)i;
                ints[i] = i;
                uints[i] = (uint)i;
                longs[i] = (long)i;
                ulongs[i] = (ulong)i;
                floats[i] = (float)(10.827 + i);
                doubles[i] = (double)(8.29 - i);
                decimals[i] = (decimal)(100.1010101010101010111 + i);
                datetimes[i] = new DateTime(1000010 + i * 10, DateTimeKind.Local);
                timespans[i] = datetimes[i] - reference;
            }
        }
    }

    [Serializable]
    public class BinaryArrays {
        public int[,] rect;
        public int[,] rectOffset;
        public int[][] jagged;
        public Array singleOffset;

        public BinaryArrays() : this(5) { }

        public BinaryArrays(int size)
        {
            rect = new int[size,size];
            rectOffset = (int[,])Array.CreateInstance(typeof(int), new int[]{size, size}, new int[]{1,1});
            for(int i = 0; i < size; ++i) {
                for(int j = 0; j < size; ++j) {
                    rect[i,j] = i*10 + j;
                    rectOffset[i+1, j+1] = i*10 + j;
                }
            }

            jagged = new int[size][];
            for(int i = 0; i < size; ++i) {
                jagged[i] = new int[i + 2];
                for(int j = 0; j < i + 2; ++j) {
                    jagged[i][j] = j;
                }
            }

            singleOffset = Array.CreateInstance(typeof(int), new int[]{size}, new int[]{1});
            for(int i = 0; i < size; ++i) {
                singleOffset.SetValue(i, i + 1);
            }
        }
    }

    [Serializable]
    public class Entity
    {
        public string entityName;
        public int level;
        public ulong xp;

        public Entity() : this("", 0, 0) { }
        public Entity(string name, int level, ulong xp) {
            entityName = name;
            this.level = level;
            this.xp = xp;
        }
    }

    [Serializable]
    public struct Tile
    {
        public int tile_id;
        public Entity entity;
    }

    [Serializable]
    class Map
    {
        public uint width, height;
        public Tile[,] tiles;

        public Map(uint width, uint height)
        {
            this.width = width;
            this.height = height;
            this.tiles = new Tile[width, height];
        }
    }

    [Serializable]
    class GameData
    {
        public Map map;
        public List<Entity> entities;

        public GameData()
        {
            map = null;
            entities = new List<Entity>();
        }
    }

    class Program
    {
        public static void Primitives()
        {
            FileStream fs = new FileStream("./primitives.dat", FileMode.OpenOrCreate);
            BinaryFormatter formatter = new BinaryFormatter();
            formatter.Serialize(fs, new Primitives(0));
        }

        public static void PrimitiveArrays()
        {
            FileStream fs = new FileStream("./primitive_arrays.dat", FileMode.OpenOrCreate);
            BinaryFormatter bf = new BinaryFormatter();
            bf.Serialize(fs, new PrimitiveArrays(5));
        }

        public static void BinaryArrays()
        {
            FileStream fs = new FileStream("./binary_arrays.dat", FileMode.OpenOrCreate);
            BinaryFormatter bf = new BinaryFormatter();
            bf.Serialize(fs, new BinaryArrays());
        }

        public static void GameExample()
        {
            GameData gd = new GameData();
            gd.map = new Map(10, 10);
            for(int i = 1; i < 10; ++i) {
                gd.map.tiles[0,i].tile_id = 1;
                gd.map.tiles[9,i].tile_id = 2;
                gd.map.tiles[i,0].tile_id = 3;
                gd.map.tiles[i,9].tile_id = 4;
            }
            gd.map.tiles[0,0].tile_id = 5;
            gd.map.tiles[0,9].tile_id = 6;
            gd.map.tiles[9,0].tile_id = 7;
            gd.map.tiles[9,9].tile_id = 8;

            gd.entities.Add(new Entity());
            gd.entities.Add(new Entity());

            gd.map.tiles[2,3].entity = gd.entities[0];
            gd.map.tiles[7,7].entity = gd.entities[1];

            FileStream fs = new FileStream("./game_data.dat", FileMode.OpenOrCreate);
            BinaryFormatter bf = new BinaryFormatter();
            bf.Serialize(fs, gd);
        }
        public static void EmptyString()
        {
            FileStream fs = new FileStream("./empty_string.dat", FileMode.OpenOrCreate);
            BinaryFormatter bf = new BinaryFormatter();
            bf.Serialize(fs, new Entity("", 1, 2));
        }

        public static void StringArray()
        {
            FileStream fs = new FileStream("./string_array.dat", FileMode.OpenOrCreate);
            BinaryFormatter bf = new BinaryFormatter();
            String[] strings = {
                "Hello World", "This is a test string", null, "", null, null, null, "Hello World", ""
            };
            bf.Serialize(fs, strings);
        }

        static void Main(string[] args)
        {
            Primitives();
            PrimitiveArrays();
            BinaryArrays();
            EmptyString();
            GameExample();
            StringArray();
        }
    }
}
