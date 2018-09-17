using System;
using System.IO;
using System.Runtime.Serialization.Formatters.Binary;

namespace TestData
{
    [Serializable]
    public struct Primitives
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
        public string null_v;
        public string string_v;
    }

    [Serializable]
    public class Entity
    {
        public string entityName;
        public int level;
        public ulong xp;
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

    class Program
    {
        public static void Primitives()
        {
            FileStream fs = new FileStream("./primitives.dat", FileMode.OpenOrCreate);
            BinaryFormatter formatter = new BinaryFormatter();
            Primitives p;
            p.bool_v = true;
            p.byte_v = 75;
            p.sbyte_v = -39;
            p.short_v = -30754;
            p.ushort_v = 61937;
            p.int_v = -2019964829;
            p.uint_v = 4082738291;
            p.long_v = -9122372936854775843;
            p.ulong_v = 17446744973709521615;
            p.float_v = 745.01f;
            p.double_v = 829.0192;
            p.decimal_v = 4310865659943.575646355933126m;
            p.null_v = null;
            p.string_v = "Hello World";

            DateTime d1 = new DateTime(1010101010, DateTimeKind.Local);
            DateTime d2 = new DateTime(685940000, DateTimeKind.Local);
            TimeSpan interval = d1 - d2;
            p.timespan_v = d1 - d2;
            p.datetime_v = d1;

            formatter.Serialize(fs, p);
        }

        public static void PrimitiveArrays()
        {
            byte[] bytes = new byte[10];
            sbyte[] sbytes = new sbyte[10];
            short[] shorts = new short[10];
            ushort[] ushorts = new ushort[10];
            int[] ints = new int[10];
            uint[] uints = new uint[10];
            long[] longs = new long[10];
            ulong[] ulongs = new ulong[10];
            float[] floats = new float[10];
            double[] doubles = new double[10];
            char[] chars = new char[10];
            TimeSpan[] times = new TimeSpan[10];
            DateTime[] datetimes = new DateTime[10];
            decimal[] decimals = new decimal[10];

            for(int i = 0; i < 10; ++i)
            {
                bytes[i] = (byte)i;
                sbytes[i] = (sbyte)(i - 5);
                shorts[i] = (short)((i - 5) * 100);
                ushorts[i] = (ushort)(i * 100);
                ints[i] = (i - 5) * 1000;
                uints[i] = (uint)(i * 1000);
                longs[i] = (long)(i - 5) * 10000;
                ulongs[i] = (ulong)i * 10000;
            }
        }

        static void Main(string[] args)
        {
            Primitives();
        }
    }
}
