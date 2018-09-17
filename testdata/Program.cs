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
    public struct PrimitiveArrays
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
            formatter.Serialize(fs, new Primitives(0));
        }

        public static void PrimitiveArrays()
        {
            FileStream fs = new FileStream("./primitive_arrays.dat", FileMode.OpenOrCreate);
            BinaryFormatter bf = new BinaryFormatter();
            bf.Serialize(fs, new PrimitiveArrays(5));
        }

        static void Main(string[] args)
        {
            Primitives();
            PrimitiveArrays();
        }
    }
}
